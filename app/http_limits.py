"""Bound provider response memory without fetching remote URLs from user input."""
import httpx

async def bounded_request(client, method, url, **kwargs):
    async with client.stream(method, url, **kwargs) as response:
        content=bytearray()
        async for chunk in response.aiter_bytes(chunk_size=65536):
            content.extend(chunk)
            if len(content)>2*1024*1024:
                raise httpx.HTTPError('Provider response exceeded the size limit.')
        headers={k:v for k,v in response.headers.items() if k.lower() not in ('content-encoding','content-length')}
        return httpx.Response(response.status_code,headers=headers,content=bytes(content))
