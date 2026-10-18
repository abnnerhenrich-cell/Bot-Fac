import unittest
import tempfile
import time
from pathlib import Path
from store import Store

class Rules(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.s=Store(str(Path(self.tmp.name)/'test.db'))
    def tearDown(self):
        self.s.db.close(); self.tmp.cleanup()
    def test_stock_cannot_go_negative(self):
        self.s.move(1,2,'estoque','radio',5,'teste')
        with self.assertRaises(ValueError): self.s.move(1,2,'estoque','radio',-6,'teste')
        self.assertEqual(self.s.one('SELECT qty FROM inventory')['qty'],5)
        self.assertEqual(len(self.s.rows('SELECT * FROM ledger')),1)
    def test_cash_and_guild_isolation(self):
        self.s.move(1,2,'caixa','RP$',10000,'teste')
        with self.assertRaises(ValueError): self.s.move(2,2,'caixa','RP$',-1,'teste')
        self.s.move(1,2,'caixa','RP$',-2000,'teste')
        self.assertEqual(self.s.balance(1),8000)
        self.assertEqual(self.s.balance(2),0)
    def test_point_unique(self):
        self.s.point(1,2,'abrir')
        with self.assertRaises(ValueError): self.s.point(1,2,'abrir')
        self.s.point(1,2,'fechar')
        with self.assertRaises(ValueError): self.s.point(1,2,'fechar')
    def test_delivery_only_once_and_approved(self):
        self.s.register(1,2,'Pedro','10')
        rid=self.s.record(1,2,'entrega',dict(item='radio',quantidade=5))
        self.assertFalse(self.s.rows('SELECT * FROM inventory'))
        self.s.review(1,3,rid,True)
        with self.assertRaises(ValueError): self.s.review(1,3,rid,True)
        self.assertEqual(self.s.one('SELECT qty FROM inventory')['qty'],5)
        self.assertEqual(len(self.s.rows('SELECT * FROM deliveries')),1)
    def test_rejected_delivery(self):
        rid=self.s.record(1,2,'entrega',dict(item='radio',quantidade=5))
        self.s.review(1,3,rid,False)
        self.assertFalse(self.s.rows('SELECT * FROM inventory'))
    def test_review_cross_guild(self):
        rid=self.s.record(1,2,'ausencia',dict(motivo='teste'))
        with self.assertRaises(ValueError): self.s.review(2,3,rid,True)
        self.assertEqual(self.s.one('SELECT status FROM records')['status'],'pendente')
    def test_recruit_conflict_rolls_back(self):
        self.s.register(1,2,'A','10')
        rid=self.s.record(1,3,'recrutamento',dict(nome='B',passaporte='10'))
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError): self.s.review(1,4,rid,True)
        self.assertEqual(self.s.one('SELECT status FROM records')['status'],'pendente')
        self.assertIsNone(self.s.member(1,3))
    def test_capacity_and_duplicate_join(self):
        cur=self.s.execute('INSERT INTO events(g,title,ts,capacity) VALUES(?,?,?,?)',(1,'Teste',int(time.time())+3600,1))
        self.s.join(1,2,cur.lastrowid)
        with self.assertRaises(ValueError): self.s.join(1,2,cur.lastrowid)
        with self.assertRaises(ValueError): self.s.join(1,3,cur.lastrowid)
        with self.assertRaises(ValueError): self.s.join(2,4,cur.lastrowid)
    def test_backup_and_restart(self):
        self.s.register(1,2,'A','10')
        path=str(Path(self.tmp.name)/'backup.db')
        self.s.backup(path)
        restored=Store(path)
        self.assertEqual(restored.member(1,2)['name'],'A')
        restored.db.close()

if __name__=='__main__': unittest.main()
