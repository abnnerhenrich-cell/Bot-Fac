"""Persistência transacional — By Diaz. Valores do caixa em centavos fictícios."""
import sqlite3
import time
import json
from pathlib import Path
from contextlib import contextmanager

SCHEMA = '''
CREATE TABLE IF NOT EXISTS config(g INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS members(g INTEGER,u INTEGER,name TEXT,rp TEXT,rank TEXT DEFAULT 'Recruta',active INTEGER DEFAULT 1,PRIMARY KEY(g,u),UNIQUE(g,rp));
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY,g INTEGER,u INTEGER,start INTEGER,end INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_shift ON shifts(g,u) WHERE end IS NULL;
CREATE TABLE IF NOT EXISTS inventory(g INTEGER,item TEXT,qty INTEGER NOT NULL CHECK(qty>=0),PRIMARY KEY(g,item));
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,g INTEGER,actor INTEGER,kind TEXT,item TEXT,amount INTEGER,reason TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,g INTEGER,u INTEGER,kind TEXT,data TEXT,status TEXT DEFAULT 'pendente',reviewer INTEGER,ts INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS one_recruit ON records(g,u) WHERE kind='recrutamento' AND status='pendente';
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,g INTEGER,title TEXT,description TEXT,ts INTEGER,capacity INTEGER,status TEXT DEFAULT 'aberta',reminded INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attendance(event INTEGER,u INTEGER,PRIMARY KEY(event,u));
CREATE TABLE IF NOT EXISTS goals(g INTEGER,item TEXT,target INTEGER CHECK(target>0),PRIMARY KEY(g,item));
CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY,g INTEGER,u INTEGER,item TEXT,qty INTEGER CHECK(qty>0),ts INTEGER);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,g INTEGER,actor INTEGER,action TEXT,detail TEXT,ts INTEGER);
CREATE TABLE IF NOT EXISTS tickets(g INTEGER,u INTEGER,channel INTEGER UNIQUE,PRIMARY KEY(g,u));
'''

class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def rows(self, sql, args=()):
        return [dict(r) for r in self.db.execute(sql, args)]

    def one(self, sql, args=()):
        rows = self.rows(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        return self.db.execute(sql, args)

    def audit(self, g, u, action, detail):
        self.execute('INSERT INTO audit(g,actor,action,detail,ts) VALUES(?,?,?,?,?)',
                     (g,u,action,str(detail),int(time.time())))

    def config(self, g):
        row = self.one('SELECT data FROM config WHERE g=?', (g,))
        return json.loads(row['data']) if row else {}

    def configure(self, g, data):
        self.execute('INSERT OR REPLACE INTO config VALUES(?,?)', (g,json.dumps(data)))

    def member(self, g, u):
        return self.one('SELECT * FROM members WHERE g=? AND u=? AND active=1', (g,u))

    def register(self, g, u, name, rp):
        self.execute('INSERT INTO members(g,u,name,rp) VALUES(?,?,?,?) ON CONFLICT(g,u) DO UPDATE SET name=excluded.name,rp=excluded.rp,active=1', (g,u,name,rp))

    def point(self, g, u, action):
        now = int(time.time())
        with self.tx():
            row = self.one('SELECT * FROM shifts WHERE g=? AND u=? AND end IS NULL',(g,u))
            if action == 'abrir':
                if row: raise ValueError('Você já tem um ponto aberto.')
                self.execute('INSERT INTO shifts(g,u,start) VALUES(?,?,?)',(g,u,now))
                result = 'Ponto aberto.'
            else:
                if not row: raise ValueError('Você não tem ponto aberto.')
                self.execute('UPDATE shifts SET end=? WHERE id=?',(now,row['id']))
                result = f"Ponto fechado: {(now-row['start'])//60} minutos."
            self.audit(g,u,'ponto '+action,result)
        return result

    def balance(self,g):
        return self.one("SELECT COALESCE(SUM(amount),0) AS total FROM ledger WHERE g=? AND kind='caixa'",(g,))['total']

    def move(self,g,u,kind,item,amount,reason):
        if not isinstance(amount,int) or amount == 0 or abs(amount)>10**12:
            raise ValueError('Quantidade/valor inválido.')
        item=item.strip().lower()
        if kind not in ('caixa','estoque'): raise ValueError('Tipo inválido.')
        with self.tx():
            if kind=='caixa':
                if self.balance(g)+amount<0: raise ValueError('Saldo insuficiente.')
            else:
                row=self.one('SELECT qty FROM inventory WHERE g=? AND item=?',(g,item))
                qty=(row['qty'] if row else 0)+amount
                if qty<0: raise ValueError('Estoque insuficiente.')
                self.execute('INSERT INTO inventory VALUES(?,?,?) ON CONFLICT(g,item) DO UPDATE SET qty=excluded.qty',(g,item,qty))
            self.execute('INSERT INTO ledger(g,actor,kind,item,amount,reason,ts) VALUES(?,?,?,?,?,?,?)',(g,u,kind,item,amount,reason,int(time.time())))
            self.audit(g,u,kind,f'{item}: {amount} | {reason}')

    def record(self,g,u,kind,data):
        with self.tx():
            cur=self.execute('INSERT INTO records(g,u,kind,data,ts) VALUES(?,?,?,?,?)',(g,u,kind,json.dumps(data,ensure_ascii=False),int(time.time())))
            self.audit(g,u,kind,cur.lastrowid)
            return cur.lastrowid

    def review(self,g,actor,rid,approve):
        with self.tx():
            r=self.one('SELECT * FROM records WHERE g=? AND id=?',(g,rid))
            if not r or r['status']!='pendente': raise ValueError('Registro inexistente ou já analisado.')
            d=json.loads(r['data'])
            if approve and r['kind']=='recrutamento': self.register(g,r['u'],d['nome'],d['passaporte'])
            if approve and r['kind']=='entrega':
                if not self.member(g,r['u']): raise ValueError('O membro não está ativo.')
                self.execute('INSERT INTO deliveries(g,u,item,qty,ts) VALUES(?,?,?,?,?)',(g,r['u'],d['item'],d['quantidade'],int(time.time())))
                self.execute('INSERT INTO inventory VALUES(?,?,?) ON CONFLICT(g,item) DO UPDATE SET qty=qty+excluded.qty',(g,d['item'],d['quantidade']))
                self.execute("INSERT INTO ledger(g,actor,kind,item,amount,reason,ts) VALUES(?,?,'estoque',?,?,?,?)",(g,actor,d['item'],d['quantidade'],f'Entrega #{rid}',int(time.time())))
            self.execute('UPDATE records SET status=?,reviewer=? WHERE id=?',('aprovado' if approve else 'recusado',actor,rid))
            self.audit(g,actor,'analisar',f'{rid}: {approve}')
            return r

    def join(self,g,u,eid):
        with self.tx():
            e=self.one("SELECT * FROM events WHERE id=? AND g=? AND status='aberta'",(eid,g))
            if not e or e['ts']<=time.time(): raise ValueError('Operação encerrada ou já iniciada.')
            if self.one('SELECT * FROM attendance WHERE event=? AND u=?',(eid,u)): raise ValueError('Você já está inscrito.')
            n=self.one('SELECT COUNT(*) n FROM attendance WHERE event=?',(eid,))['n']
            if n>=e['capacity']: raise ValueError('Operação lotada.')
            self.execute('INSERT INTO attendance VALUES(?,?)',(eid,u))
            self.audit(g,u,'inscrever',eid)

    def backup(self,path):
        with sqlite3.connect(path) as dest: self.db.backup(dest)
