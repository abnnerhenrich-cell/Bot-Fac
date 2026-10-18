"""Validação local sem conexão nem token do Discord."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
_tmp=tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH']=str(Path(_tmp.name)/'bot.db')
os.environ['GUILD_ID']='123'
import bot as app

class DiscordRules(unittest.IsolatedAsyncioTestCase):
    async def test_all_commands_serialize(self):
        commands=app.bot.tree.get_commands()
        self.assertGreaterEqual(len(commands),20)
        for command in commands:
            payload=command.to_dict(app.bot.tree)
            self.assertLessEqual(len(payload.get('options',[])),25)
            self.assertTrue(payload['description'])
        self.assertTrue(app.Panel().is_persistent())
    async def test_privilege_checks(self):
        app.DB.configure(123,{'staff':99})
        user=SimpleNamespace(id=7,roles=[],guild_permissions=SimpleNamespace(administrator=False))
        i=SimpleNamespace(guild=SimpleNamespace(id=123),user=user)
        with self.assertRaises(ValueError): await app.guard(i)
        with self.assertRaises(ValueError): await app.guard(i,staff=True)
        await app.guard(i,member=False)
        app.DB.register(123,7,'Membro','7')
        await app.guard(i)
        with self.assertRaises(ValueError): await app.guard(i,staff=True)
        user.roles=[SimpleNamespace(id=99)]
        await app.guard(i,staff=True)
        with self.assertRaises(ValueError): await app.guard(i,admin=True)
        i.guild=SimpleNamespace(id=456)
        with self.assertRaises(ValueError): await app.guard(i,member=False)
    async def test_csv_formula_injection(self):
        data=app.csv_bytes([{'nome':'=1+1','id':123}]).decode('utf-8-sig')
        self.assertIn("'=1+1",data)

def tearDownModule():
    app.DB.db.close()
    _tmp.cleanup()

if __name__=='__main__': unittest.main()
