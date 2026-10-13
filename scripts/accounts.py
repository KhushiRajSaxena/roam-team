"""Local-only account administration: no public registration or admin API."""
import argparse
import getpass
import secrets
from app.security import SecurityStore

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['create','reset','disable','revoke','revoke-all','bootstrap'])
    parser.add_argument('username',nargs='?')
    args=parser.parse_args();store=SecurityStore()
    if args.action=='bootstrap':
        with store.connection() as db:
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
                print('Accounts already configured.');return
        password=secrets.token_urlsafe(24)
        store.create_user('owner',password)
        path=store.path.parent/'owner-login.txt'
        with path.open('x') as f:
            path.chmod(0o600);f.write('Username: owner\nPassword: '+password+'\n\nKeep this file private. Reset with: .venv/bin/python -m scripts.accounts reset owner\n')
        print('Owner account created. Credentials are in .local/owner-login.txt (not printed).');return
    if args.action=='revoke-all':
        with store.connection() as db:db.execute('DELETE FROM sessions')
        print('All sessions revoked.');return
    if not args.username:parser.error('username is required')
    if args.action=='create':
        store.create_user(args.username,getpass.getpass('New password (14+ characters): '));print('Account created.');return
    with store.connection() as db:
        row=db.execute('SELECT id FROM users WHERE username=?',(args.username,)).fetchone()
        if not row:parser.error('Unknown username')
        if args.action=='reset':
            password=getpass.getpass('New password (14+ characters): ')
            if not 14<=len(password)<=128:parser.error('Password must be 14-128 characters')
            salt=secrets.token_hex(16)
            db.execute('UPDATE users SET salt=?,password=?,disabled=0 WHERE id=?',(salt,store.password_hash(password,salt),row[0]))
        if args.action=='disable':db.execute('UPDATE users SET disabled=1 WHERE id=?',(row[0],))
        db.execute('DELETE FROM sessions WHERE user_id=?',(row[0],))
    print('Updated account; its sessions are revoked.')

if __name__=='__main__':main()
