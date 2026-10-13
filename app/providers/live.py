"""Quota-bounded SerpApi searches and Geoapify place/route discovery."""
from app.settings import setting
import asyncio
import hashlib
import math
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
import httpx
from app.http_limits import bounded_request
from app.models import CITIES, Offer
from app.services.cache import Store, QuotaError
from .errors import ProviderError


def paise(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0: raise ValueError('Invalid amount')
    return int((number * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def https_url(value):
    if not isinstance(value, str): return None
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.netloc or parts.username: return None
    params = [(k,v) for k,v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in ('api_key','apikey','key')]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def scrub(value, secrets):
    if isinstance(value, dict):
        return {k:scrub(v,secrets) for k,v in value.items() if k.lower() not in ('api_key','apikey','account_email','account_id')}
    if isinstance(value, list): return [scrub(v,secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret: value = value.replace(secret, '[redacted]')
        return value
    return value


def offer_id(prefix, value): return prefix + '-' + hashlib.sha256(str(value).encode()).hexdigest()[:16]
def stamp(value): return datetime.fromtimestamp(value, timezone.utc).isoformat()
def local_time(value): return datetime.fromisoformat(value).replace(tzinfo=None)


class LiveProvider:
    def __init__(self, client=None, store=None):
        self.serp_key = setting('SERPAPI_API_KEY')
        self.geo_key = setting('GEOAPIFY_API_KEY')
        self.client = client or httpx.AsyncClient(timeout=50)
        self.store = store or Store()
        self.counts = {'serpapi_requests':0,'geoapify_requests':0,'travel_cache_hits':0}
        self.warnings = []

    async def close(self): await self.client.aclose()

    async def _json(self, url, params):
        try:
            response = await bounded_request(self.client, 'GET', url, params=params)
            if response.status_code == 429:
                raise ProviderError('Provider rate limit reached. Wait before retrying; no automatic search retry was made.')
            if response.status_code in (401,403): raise ProviderError('Provider rejected the API key or account access.')
            if response.is_error: raise ProviderError(f'Travel provider returned HTTP {response.status_code}. No sample data was substituted.')
            data = response.json()
            if not isinstance(data, dict): raise ProviderError('Travel provider returned an unexpected response.')
            if data.get('error'):
                # No-result responses are valid negative cache entries, not retry triggers.
                if 'hasn\'t returned any results' in str(data['error']).lower(): return {'empty':True}
                raise ProviderError('Provider could not complete this search. Check the route, dates and API access.')
            return scrub(data, [self.serp_key,self.geo_key])
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError('Travel provider could not be reached or returned invalid data. No automatic retry was made.') from None

    async def account(self):
        if not self.serp_key: raise ProviderError('SERPAPI_API_KEY is missing.')
        async def fetch():
            data = await self._json('https://serpapi.com/account.json', {'api_key':self.serp_key})
            # Only non-sensitive quota fields may leave this method.
            return {k:data.get(k) for k in ('plan_searches_left','searches_per_month','this_month_usage','plan_renewal_date')}
        data, _, _ = await self.store.cached('serpapi_account', {}, self.serp_key, 60, fetch)
        return data

    async def serp(self, params):
        async def fetch():
            account = await self.account()
            remaining = account.get('plan_searches_left')
            if not isinstance(remaining, (int,float)) or remaining <= 20:
                raise ProviderError('SerpApi free-plan reserve reached or balance unavailable. Keep the last 20 searches; cached results still work.')
            if self.counts['serpapi_requests'] >= 3:
                raise ProviderError('This trip reached its three-search SerpApi limit.')
            self.store.consume_balance(self.store.cache_key('serpapi_account', {}, self.serp_key))
            self.counts['serpapi_requests'] += 1
            return await self._json('https://serpapi.com/search.json', {**params,'api_key':self.serp_key})
        try:
            data, hit, created = await self.store.cached('serpapi', params, self.serp_key, 6*3600, fetch)
        except QuotaError as exc: raise ProviderError(str(exc)) from None
        self.counts['travel_cache_hits'] += int(hit)
        return data, created

    async def geo(self, path, params, ttl=7*86400):
        if not self.geo_key: raise ProviderError('GEOAPIFY_API_KEY is missing.')
        async def fetch():
            self.counts['geoapify_requests'] += 1
            return await self._json('https://api.geoapify.com'+path, {**params,'apiKey':self.geo_key})
        try:
            data, hit, created = await self.store.cached('geoapify', {'path':path,**params}, self.geo_key, ttl, fetch)
        except QuotaError as exc: raise ProviderError(str(exc)) from None
        self.counts['travel_cache_hits'] += int(hit)
        return data, created

    async def search_flights(self, trip):
        params = {'engine':'google_flights','departure_id':trip.origin,'arrival_id':trip.destination,
                  'outbound_date':str(trip.start),'return_date':str(trip.end),'type':1,
                  'adults':trip.travelers,'currency':'INR','gl':'in','hl':'en'}
        data, created = await self.serp(params)
        if not data.get('empty') and data.get('search_parameters',{}).get('currency') != 'INR':
            raise ProviderError('Flight response did not confirm INR; refusing to mix currencies.')
        valid = []
        for row in data.get('best_flights',[]) + data.get('other_flights',[]):
            try:
                first,last=row['flights'][0],row['flights'][-1]
                arrival=local_time(last['arrival_airport']['time'])
                if arrival.date()!=trip.start or arrival.hour>=21: continue
                if first['departure_airport']['id']!=trip.origin or last['arrival_airport']['id']!=trip.destination: continue
                if not row.get('departure_token'): continue
                valid.append((paise(row['price']),row))
            except (KeyError,ValueError,TypeError,IndexError,ArithmeticError): continue
        if not valid: return []
        # Expand only one valid outbound, avoiding N searches for N alternatives.
        _, outbound = min(valid,key=lambda pair:pair[0])
        returned, return_created = await self.serp({**params,'departure_token':outbound['departure_token']})
        if not returned.get('empty') and returned.get('search_parameters',{}).get('currency') != 'INR':
            raise ProviderError('Return-flight response did not confirm INR.')
        offers=[]
        for row in returned.get('best_flights',[]) + returned.get('other_flights',[]):
            try:
                first,last=row['flights'][0],row['flights'][-1]
                departure=local_time(first['departure_airport']['time'])
                if departure.date()!=trip.end or departure.hour<3: continue
                if first['departure_airport']['id']!=trip.destination or last['arrival_airport']['id']!=trip.origin: continue
                names=list(dict.fromkeys(s.get('airline','Airline') for s in outbound['flights']+row['flights']))
                offers.append(Offer(id=offer_id('flight',row.get('booking_token') or row['flights']),category='flights',
                    title=' / '.join(names),cost=paise(row['price']),
                    description=f'Round-trip search total for {trip.travelers} adult(s). One lowest-priced valid outbound was expanded to conserve searches. Confirm fare, baggage and passenger total with the booking provider.',
                    arrival=local_time(outbound['flights'][-1]['arrival_airport']['time']).isoformat(),
                    outbound_departure=local_time(outbound['flights'][0]['departure_airport']['time']).isoformat(),
                    departure=departure.isoformat(),return_arrival=local_time(last['arrival_airport']['time']).isoformat(),
                    source='Google Flights via SerpApi',sample=False,price_kind='search_price',retrieved_at=stamp(min(created,return_created)),
                    url=https_url(returned.get('search_metadata',{}).get('google_flights_url') or data.get('search_metadata',{}).get('google_flights_url'))))
            except (KeyError,ValueError,TypeError,IndexError,ArithmeticError): continue
        return sorted(offers,key=lambda o:o.cost)[:8]

    async def search_stays(self, trip):
        city=CITIES[trip.destination]
        params={'engine':'google_hotels','q':f"Hotels in {city['name']}, {city['country']}",
                'check_in_date':str(trip.start),'check_out_date':str(trip.end),'adults':trip.travelers,
                'currency':'INR','gl':'in','hl':'en','sort_by':3}
        data,created=await self.serp(params)
        if not data.get('empty') and data.get('search_parameters',{}).get('currency')!='INR':
            raise ProviderError('Hotel response did not confirm INR; refusing to mix currencies.')
        offers=[]
        for row in data.get('properties',[]):
            try:
                total=row.get('total_rate',{}).get('extracted_lowest')
                estimated=total is None
                cost=paise(row['rate_per_night']['extracted_lowest'])*trip.nights if estimated else paise(total)
                if not cost: continue
                coords=row.get('gps_coordinates',{})
                offers.append(Offer(id=offer_id('stay',row.get('property_token') or row['name']),category='stays',title=row['name'],cost=cost,
                    description=f"{trip.nights} nights · search requested for {trip.travelers} adult(s). "+
                        ('Estimated from nightly rate × nights. ' if estimated else 'Listed whole-stay rate. ')+
                        'Confirm room configuration, taxes, cancellation and final total before booking.',
                    source='Google Hotels via SerpApi',sample=False,price_kind='estimate' if estimated else 'search_price',retrieved_at=stamp(created),
                    url=https_url(row.get('link')) or 'https://www.google.com/travel/hotels?'+urlencode({'q':row['name']+' '+city['name']}),
                    location=row.get('description') or city['name'],latitude=coords.get('latitude'),longitude=coords.get('longitude'),rating=row.get('overall_rating')))
            except (KeyError,ValueError,TypeError,ArithmeticError): continue
        return sorted(offers,key=lambda o:o.cost)[:8]

    async def search_activities(self, trip):
        city=CITIES[trip.destination]
        if city.get('geocode'):
            # Airport coordinates are often far from the city. Resolve its center only
            # when planning a live trip; typing in either location field is offline.
            data, _ = await self.geo('/v1/geocode/search', {
                'city': city['name'], 'country': city['country'], 'type': 'city',
                'filter': 'countrycode:' + city['country_code'].lower(),
                'bias': f"proximity:{city['lon']},{city['lat']}", 'limit': 1,
                'format': 'json'}, 30*86400)
            results = data.get('results', [])
            if not results:
                raise ProviderError('Could not locate the destination city for activities. Try another nearby airport.')
            center = results[0]
            if center.get('country_code', '').upper() != city['country_code']:
                raise ProviderError('Destination lookup returned a different country.')
            lat, lon = center.get('lat'), center.get('lon')
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ProviderError('Destination lookup returned invalid coordinates.')
            city = {**city, 'lat': lat, 'lon': lon}
        params={'categories':'tourism.sights,entertainment.museum,leisure.park',
                'filter':f"circle:{city['lon']},{city['lat']},8000",'bias':f"proximity:{city['lon']},{city['lat']}",
                'limit':20,'lang':'en'}
        data,created=await self.geo('/v2/places',params)
        offers=[]
        for row in data.get('features',[]):
            try:
                prop=row['properties'];raw=prop.get('datasource',{}).get('raw',{})
                if not prop.get('name'): continue
                coords=row['geometry']['coordinates']
                categories=prop.get('categories',[])
                free=str(raw.get('fee','')).lower()=='no'
                # Unknown entry fees are NEVER interpreted as free.
                allowance=0 if free else max(300,city['daily']//2)*100*trip.travelers
                offers.append(Offer(id=offer_id('activity',prop['place_id']),category='activities',title=prop['name'],cost=allowance,
                    description=('Source lists no entrance fee; reconfirm before visiting. ' if free else 'Entry fee unknown. Includes a planning allowance, not a ticket quote. ')+
                        'Two-hour visit suggested; opening hours and admission need confirmation.',
                    source='Geoapify / OpenStreetMap',sample=False,price_kind='listed_free' if free else 'estimate',retrieved_at=stamp(created),
                    latitude=coords[1],longitude=coords[0],location=prop.get('formatted',city['name']),
                    opening_hours=prop.get('opening_hours') or raw.get('opening_hours'),
                    url=https_url(prop.get('website') or raw.get('website')) or f'https://www.openstreetmap.org/?mlat={coords[1]}&mlon={coords[0]}#map=17/{coords[1]}/{coords[0]}',
                    tags=['nature' if any('park' in c or 'natural' in c for c in categories) else 'culture']))
            except (KeyError,ValueError,TypeError,IndexError): continue
        # Preferences are applied after retrieval, so changing interests is a cache hit.
        unique={o.id:o for o in offers}
        return sorted(unique.values(),key=lambda o:(not bool(set(o.tags)&set(trip.interests)),o.cost))[:10]

    async def route(self, points):
        if len(points)<2: return None
        params={'waypoints':'|'.join(f'{lat:.5f},{lon:.5f}' for lat,lon in points),'mode':'drive','format':'geojson'}
        data,created=await self.geo('/v1/routing',params,86400)
        features=data.get('features',[])
        if not features: return None
        prop=features[0].get('properties',{})
        legs=prop.get('legs',[])
        if len(legs)!=len(points)-1 or any('time' not in leg for leg in legs): return None
        return {'legs':[{'minutes':math.ceil(leg['time']/60),'distance_m':leg.get('distance')} for leg in legs],
                'source':'Geoapify routing; driving estimate, not live traffic','retrieved_at':stamp(created)}
