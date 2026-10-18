"""Central de facção GTA RP — By Diaz."""
import os
import io
import csv
import json
import time
import asyncio
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from store import Store

load_dotenv()
log = logging.getLogger('faccao')
DB = Store(os.getenv('DATABASE_PATH','data/faccao.sqlite3'))
TZ = ZoneInfo('America/Sao_Paulo')


def embed(title, text):
    e=discord.Embed(title=title,description=str(text)[:4000],color=0x8B5CF6)
    e.set_footer(text='Central de Facção • GTA RP • By Diaz')
    return e

async def reply(i, text, title='Central de Facção', **kwargs):
    send=i.followup.send if i.response.is_done() else i.response.send_message
    await send(embed=embed(title,text),ephemeral=True,**kwargs)

async def guard(i, staff=False, admin=False, member=True):
    if not i.guild or i.guild.id!=int(os.getenv('GUILD_ID','0')):
        raise ValueError('Use o bot no servidor configurado.')
    cfg=DB.config(i.guild.id)
    is_admin=i.user.guild_permissions.administrator
    if admin and not is_admin: raise ValueError('Apenas administradores.')
    leadership=is_admin or any(r.id==cfg.get('staff') for r in i.user.roles)
    if staff and not leadership: raise ValueError('Apenas a liderança pode fazer isso.')
    if member and not leadership and not DB.member(i.guild.id,i.user.id):
        raise ValueError('Seu cadastro ainda não foi aprovado.')
    return cfg

async def notify(g,text):
    cfg=DB.config(g.id)
    channel=g.get_channel(cfg.get('logs',0))
    if channel:
        try: await channel.send(embed=embed('Registro',text))
        except discord.HTTPException: log.warning('Não foi possível enviar log ao Discord.')

class SafeView(discord.ui.View):
    async def on_error(self,i,error,item):
        await handle_error(i,error)

async def handle_error(i,error):
    error=getattr(error,'original',error)
    if isinstance(error,(ValueError,app_commands.CheckFailure)):
        message=str(error)
    elif isinstance(error,sqlite3.IntegrityError):
        message='Registro duplicado ou conflitante. Confira passaporte, cadastro e pedidos pendentes.'
    elif isinstance(error,discord.Forbidden):
        message='O bot não tem permissão. Confira os canais e a posição do cargo do bot.'
    else:
        log.error('Falha na interação',exc_info=(type(error),error,error.__traceback__))
        message='Não foi possível concluir. Consulte o console antes de tentar novamente.'
    await reply(i,message,'Aviso')

class Recruit(discord.ui.Modal,title='Recrutamento • By Diaz'):
    nome=discord.ui.TextInput(label='Nome do personagem',max_length=60)
    passaporte=discord.ui.TextInput(label='Passaporte / ID no RP',max_length=24)
    experiencia=discord.ui.TextInput(label='Experiência e disponibilidade',style=discord.TextStyle.paragraph,max_length=700)
    async def on_submit(self,i):
        await guard(i,member=False)
        if DB.member(i.guild_id,i.user.id): raise ValueError('Você já é membro cadastrado.')
        rid=DB.record(i.guild_id,i.user.id,'recrutamento',{'nome':self.nome.value,'passaporte':self.passaporte.value,'experiencia':self.experiencia.value})
        await reply(i,f'Inscrição #{rid} enviada. Aguarde a liderança.')
        await notify(i.guild,f'Novo recrutamento #{rid} de <@{i.user.id}>. Use /registros e /analisar.')
    async def on_error(self,i,error): await handle_error(i,error)

class Panel(SafeView):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label='Recrutamento',style=discord.ButtonStyle.primary,custom_id='diaz:recruit')
    async def recruit(self,i,b):
        await guard(i,member=False)
        await i.response.send_modal(Recruit())
    @discord.ui.button(label='Abrir ponto',style=discord.ButtonStyle.success,custom_id='diaz:in')
    async def clock_in(self,i,b):
        await guard(i)
        await reply(i,DB.point(i.guild_id,i.user.id,'abrir'))
    @discord.ui.button(label='Fechar ponto',style=discord.ButtonStyle.danger,custom_id='diaz:out')
    async def clock_out(self,i,b):
        await guard(i)
        await reply(i,DB.point(i.guild_id,i.user.id,'fechar'))
    @discord.ui.button(label='Meu perfil',custom_id='diaz:profile')
    async def profile(self,i,b):
        await guard(i)
        await profile_response(i,i.user)
    @discord.ui.button(label='Atendimento',custom_id='diaz:ticket')
    async def ticket(self,i,b):
        await open_ticket(i)

class FactionBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(Panel())
        guild=discord.Object(id=int(os.environ['GUILD_ID']))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        maintenance.start()
    async def on_ready(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,name='By Diaz'))
        log.info('Online como %s | By Diaz', self.user)

intents=discord.Intents.default()
intents.message_content=True
bot=FactionBot(command_prefix=commands.when_mentioned,intents=intents,allowed_mentions=discord.AllowedMentions.none())
bot.tree.error(handle_error)

@bot.tree.command(name='configurar',description='Configuração inicial e canais • Administrador')
@app_commands.default_permissions(administrator=True)
async def configure(i:discord.Interaction,nome:str,lideranca:discord.Role,membro:discord.Role,logs:discord.TextChannel,avisos:discord.TextChannel,tickets:discord.CategoryChannel):
    await guard(i,admin=True,member=False)
    if lideranca.is_default() or membro.is_default() or lideranca==membro:
        raise ValueError('Use cargos distintos, sem @everyone.')
    if membro.managed or membro.permissions.administrator or membro.permissions.manage_roles or membro.permissions.manage_guild:
        raise ValueError('O cargo de membro não pode ser gerenciado nem ter permissões administrativas.')
    if membro>=i.guild.me.top_role: raise ValueError('Coloque o cargo do bot acima do cargo de membro.')
    DB.configure(i.guild_id,dict(name=nome[:80],staff=lideranca.id,member=membro.id,logs=logs.id,announcements=avisos.id,tickets=tickets.id))
    DB.audit(i.guild_id,i.user.id,'configurar',nome)
    await reply(i,'Configuração salva. Use /painel para publicar os botões.')

@bot.tree.command(name='painel',description='Publicar painel com botões persistentes')
async def panel(i:discord.Interaction,canal:discord.TextChannel):
    cfg=await guard(i,staff=True)
    await canal.send(embed=embed(cfg.get('name','Facção'),'Central de gerenciamento GTA RP\n\nRecrutamento • Ponto • Perfil • Atendimento\nUse /ajuda para ver todos os módulos.'),view=Panel())
    await reply(i,'Painel publicado.')

@bot.tree.command(name='ajuda',description='Comandos e instruções da facção')
async def help_cmd(i:discord.Interaction):
    await guard(i,member=False)
    await reply(i,'**Membros:** /perfil, /ponto, /ranking, /entrega, /metas, /ausencia, /operacao listar ou entrar ou sair, /ticket.\n**Liderança:** /membro, /registros, /analisar, /estoque, /caixa, /meta, /advertencia, /operacao criar ou encerrar, /relatorio, /aviso, /ponto_corrigir.\n**Administrador:** /configurar e /backup.\nO painel possui formulário de recrutamento. Todos os valores e itens são do RP.','Ajuda • By Diaz')

async def profile_response(i,user):
    m=DB.member(i.guild_id,user.id)
    if not m: raise ValueError('Membro não cadastrado.')
    now=int(time.time())
    total=DB.one('SELECT COALESCE(SUM(COALESCE(end,?)-start),0) n FROM shifts WHERE g=? AND u=?',(now,i.guild_id,user.id))['n']
    warns=DB.one("SELECT COUNT(*) n FROM records WHERE g=? AND u=? AND kind='advertencia' AND status='pendente'",(i.guild_id,user.id))['n']
    await reply(i,f"**Personagem:** {m['name']}\n**Passaporte:** {m['rp']}\n**Patente:** {m['rank']}\n**Horas totais:** {total/3600:.2f}\n**Advertências ativas:** {warns}",'Perfil')

@bot.tree.command(name='perfil',description='Ver perfil de membro')
async def profile(i:discord.Interaction,usuario:discord.Member|None=None):
    await guard(i)
    if usuario and usuario.id!=i.user.id: await guard(i,staff=True)
    await profile_response(i,usuario or i.user)

@bot.tree.command(name='membro',description='Cadastrar, alterar patente ou desligar membro')
async def member_cmd(i:discord.Interaction,acao:Literal['cadastrar','patente','desligar'],usuario:discord.Member,nome:str='',passaporte:str='',patente:str=''):
    cfg=await guard(i,staff=True)
    role=i.guild.get_role(cfg.get('member',0))
    await i.response.defer(ephemeral=True)
    if acao=='cadastrar':
        if not nome.strip() or not passaporte.strip(): raise ValueError('Informe nome e passaporte.')
        DB.register(i.guild_id,usuario.id,nome[:60],passaporte[:24])
        result='Cadastro salvo.'
        if role:
            try: await usuario.add_roles(role,reason='Cadastro RP • By Diaz')
            except discord.HTTPException: result+=' Cargo não aplicado; corrija a hierarquia e repita o cadastro.'
    else:
        if not DB.member(i.guild_id,usuario.id): raise ValueError('Membro não cadastrado.')
        if acao=='patente':
            if not patente.strip(): raise ValueError('Informe a patente.')
            DB.execute('UPDATE members SET rank=? WHERE g=? AND u=?',(patente[:60],i.guild_id,usuario.id))
            result='Patente interna atualizada (não altera cargos do Discord).'
        else:
            with DB.tx():
                DB.execute('UPDATE members SET active=0 WHERE g=? AND u=?',(i.guild_id,usuario.id))
                DB.execute('UPDATE shifts SET end=? WHERE g=? AND u=? AND end IS NULL',(int(time.time()),i.guild_id,usuario.id))
            result='Membro desligado e ponto fechado.'
            if role:
                try: await usuario.remove_roles(role,reason='Desligamento RP')
                except discord.HTTPException: result+=' Remova o cargo manualmente; o bot não conseguiu removê-lo.'
    DB.audit(i.guild_id,i.user.id,'membro '+acao,usuario.id)
    await reply(i,result)
    await notify(i.guild,f'{acao}: <@{usuario.id}> por <@{i.user.id}>.')

@bot.tree.command(name='ponto',description='Abrir, fechar ou consultar ponto')
async def point(i:discord.Interaction,acao:Literal['abrir','fechar','status']):
    await guard(i)
    if acao=='status':
        r=DB.one('SELECT start FROM shifts WHERE g=? AND u=? AND end IS NULL',(i.guild_id,i.user.id))
        await reply(i,f"Aberto desde <t:{r['start']}:f>." if r else 'Nenhum ponto aberto.')
    else: await reply(i,DB.point(i.guild_id,i.user.id,acao))

@bot.tree.command(name='ponto_corrigir',description='Encerrar ponto esquecido usando duração total em minutos')
async def fix_point(i:discord.Interaction,usuario:discord.Member,minutos:app_commands.Range[int,0,1440],motivo:str):
    await guard(i,staff=True)
    with DB.tx():
        r=DB.one('SELECT * FROM shifts WHERE g=? AND u=? AND end IS NULL',(i.guild_id,usuario.id))
        if not r: raise ValueError('Nenhum ponto aberto para esse membro.')
        end=r['start']+minutos*60
        if end>time.time(): raise ValueError('Duração ultrapassa o horário atual.')
        DB.execute('UPDATE shifts SET end=? WHERE id=?',(end,r['id']))
        DB.audit(i.guild_id,i.user.id,'corrigir ponto',f'{usuario.id}: {minutos}min | {motivo}')
    await reply(i,'Ponto corrigido e auditado.')

@bot.tree.command(name='ranking',description='Ranking de horas por período, incluindo ponto em andamento')
async def ranking(i:discord.Interaction,dias:app_commands.Range[int,1,365]=7):
    await guard(i)
    now=int(time.time()); since=now-dias*86400
    rows=DB.rows('SELECT u,SUM(COALESCE(end,?)-MAX(start,?)) total FROM shifts WHERE g=? AND COALESCE(end,?)>? GROUP BY u ORDER BY total DESC LIMIT 20',(now,since,i.guild_id,now,since))
    await reply(i,'\n'.join(f"{n}. <@{r['u']}> — {r['total']/3600:.2f}h" for n,r in enumerate(rows,1)) or 'Sem registros.',f'Ranking • {dias} dias')

@bot.tree.command(name='estoque',description='Consultar ou movimentar estoque fictício do RP')
async def stock(i:discord.Interaction,acao:Literal['ver','entrada','saida'],item:str='',quantidade:app_commands.Range[int,1,1000000]=1,motivo:str='Ajuste de estoque RP'):
    await guard(i,staff=True)
    if acao=='ver':
        rows=DB.rows('SELECT * FROM inventory WHERE g=? ORDER BY item LIMIT 60',(i.guild_id,))
        await reply(i,'\n'.join(f"{r['item']}: **{r['qty']}**" for r in rows) or 'Estoque vazio.','Estoque • até 60 itens')
    else:
        if not item.strip() or len(item)>60: raise ValueError('Informe item de até 60 caracteres.')
        DB.move(i.guild_id,i.user.id,'estoque',item,quantidade*(1 if acao=='entrada' else -1),motivo[:300])
        await reply(i,'Movimentação salva.')
        await notify(i.guild,f'Estoque: {acao} de {quantidade} {item}, por <@{i.user.id}>.')

@bot.tree.command(name='caixa',description='Saldo e movimentações de dinheiro fictício do RP')
async def cash(i:discord.Interaction,acao:Literal['saldo','entrada','saida'],valor:app_commands.Range[int,1,100000000]=1,motivo:str='Movimentação RP'):
    await guard(i,staff=True)
    if acao!='saldo': DB.move(i.guild_id,i.user.id,'caixa','RP$',valor*100*(1 if acao=='entrada' else -1),motivo[:300])
    await reply(i,f'Saldo: RP$ {DB.balance(i.guild_id)/100:,.2f}\nValores fictícios. Nenhuma integração bancária.','Caixa')

@bot.tree.command(name='entrega',description='Enviar produção para aprovação da liderança')
async def delivery(i:discord.Interaction,item:str,quantidade:app_commands.Range[int,1,1000000],comprovante:discord.Attachment|None=None):
    await guard(i)
    if not item.strip() or len(item)>60: raise ValueError('Item deve ter entre 1 e 60 caracteres.')
    rid=DB.record(i.guild_id,i.user.id,'entrega',dict(item=item.strip().lower(),quantidade=quantidade,comprovante=comprovante.url if comprovante else 'Não enviado'))
    await reply(i,f'Entrega #{rid} aguardando aprovação. Só entregas aprovadas contam para metas e estoque.')
    await notify(i.guild,f'Entrega #{rid} de <@{i.user.id}> aguardando análise.')

@bot.tree.command(name='meta',description='Definir meta semanal de produção por membro e item')
async def goal(i:discord.Interaction,item:str,quantidade:app_commands.Range[int,1,1000000]):
    await guard(i,staff=True)
    if not item.strip() or len(item)>60: raise ValueError('Item deve ter entre 1 e 60 caracteres.')
    DB.execute('INSERT INTO goals VALUES(?,?,?) ON CONFLICT(g,item) DO UPDATE SET target=excluded.target',(i.guild_id,item.strip().lower(),quantidade))
    DB.audit(i.guild_id,i.user.id,'meta',f'{item}: {quantidade}')
    await reply(i,'Meta definida para os últimos 7 dias (janela móvel).')

@bot.tree.command(name='metas',description='Consultar progresso individual nos últimos sete dias')
async def goals(i:discord.Interaction):
    await guard(i)
    rows=DB.rows('SELECT goals.item,target,COALESCE(SUM(d.qty),0) done FROM goals LEFT JOIN deliveries d ON d.g=goals.g AND d.item=goals.item AND d.u=? AND d.ts>=? WHERE goals.g=? GROUP BY goals.item,target',(i.user.id,int(time.time())-604800,i.guild_id))
    await reply(i,'\n'.join(f"{r['item']}: {r['done']}/{r['target']} ({r['done']/r['target']:.0%})" for r in rows) or 'Nenhuma meta definida.','Suas metas')

@bot.tree.command(name='ausencia',description='Solicitar afastamento temporário')
async def absence(i:discord.Interaction,motivo:str,retorno:str):
    await guard(i)
    dt=datetime.strptime(retorno,'%d/%m/%Y').replace(tzinfo=TZ)
    if dt.timestamp()<=time.time(): raise ValueError('Informe retorno futuro em DD/MM/AAAA.')
    rid=DB.record(i.guild_id,i.user.id,'ausencia',dict(motivo=motivo[:700],retorno=retorno))
    await reply(i,f'Ausência #{rid} enviada para análise.')

@bot.tree.command(name='registros',description='Listar solicitações e advertências com paginação')
async def records(i:discord.Interaction,tipo:Literal['recrutamento','entrega','ausencia','advertencia'],pagina:app_commands.Range[int,1,100000]=1):
    await guard(i,staff=True)
    rows=DB.rows('SELECT * FROM records WHERE g=? AND kind=? ORDER BY id DESC LIMIT 5 OFFSET ?',(i.guild_id,tipo,(pagina-1)*5))
    await reply(i,'\n\n'.join(f"**#{r['id']} • <@{r['u']}> • {r['status']}**\n{r['data'][:550]}" for r in rows) or 'Sem registros.',f'{tipo} • página {pagina}')

@bot.tree.command(name='analisar',description='Aprovar ou recusar inscrição, entrega ou ausência')
async def review(i:discord.Interaction,registro:int,decisao:Literal['aprovar','recusar']):
    cfg=await guard(i,staff=True)
    r=DB.one('SELECT kind FROM records WHERE g=? AND id=?',(i.guild_id,registro))
    if r and r['kind']=='advertencia': raise ValueError('Use /advertencia revogar.')
    await i.response.defer(ephemeral=True)
    r=DB.review(i.guild_id,i.user.id,registro,decisao=='aprovar')
    extra=''
    if r['kind']=='recrutamento' and decisao=='aprovar':
        role=i.guild.get_role(cfg.get('member',0))
        try:
            user=await i.guild.fetch_member(r['u'])
            if role: await user.add_roles(role,reason=f'Recrutamento #{registro}')
        except discord.HTTPException: extra=' Cadastro salvo, mas cargo não aplicado. Use /membro cadastrar para tentar novamente.'
    await reply(i,f'Registro #{registro}: {decisao}.{extra}')
    await notify(i.guild,f'Registro #{registro}: {decisao}, por <@{i.user.id}>.')

@bot.tree.command(name='advertencia',description='Aplicar ou revogar advertência interna')
async def warning(i:discord.Interaction,acao:Literal['aplicar','revogar'],usuario:discord.Member,motivo:str,registro:int=0):
    await guard(i,staff=True)
    if acao=='aplicar':
        if not DB.member(i.guild_id,usuario.id): raise ValueError('Membro não cadastrado.')
        rid=DB.record(i.guild_id,usuario.id,'advertencia',dict(motivo=motivo[:700],autor=i.user.id))
        await reply(i,f'Advertência #{rid} registrada. Nenhum banimento automático.')
    else:
        with DB.tx():
            cur=DB.execute("UPDATE records SET status='revogada',reviewer=? WHERE g=? AND id=? AND u=? AND kind='advertencia' AND status='pendente'",(i.user.id,i.guild_id,registro,usuario.id))
            if not cur.rowcount: raise ValueError('Advertência ativa não encontrada.')
            DB.audit(i.guild_id,i.user.id,'revogar advertencia',f'{registro}: {motivo}')
        await reply(i,'Advertência revogada.')

@bot.tree.command(name='operacao',description='Agenda de eventos RP e inscrições com limite de vagas')
async def operation(i:discord.Interaction,acao:Literal['criar','listar','entrar','sair','encerrar','participantes'],operacao:int=0,titulo:str='',data:str='',vagas:app_commands.Range[int,1,200]=20,descricao:str=''):
    await guard(i,staff=acao in ('criar','encerrar'))
    if acao=='criar':
        if not titulo.strip(): raise ValueError('Informe o título.')
        ts=int(datetime.strptime(data,'%d/%m/%Y %H:%M').replace(tzinfo=TZ).timestamp())
        if ts<=time.time(): raise ValueError('Escolha uma data futura: DD/MM/AAAA HH:MM (Brasília).')
        cur=DB.execute('INSERT INTO events(g,title,description,ts,capacity) VALUES(?,?,?,?,?)',(i.guild_id,titulo[:100],descricao[:700],ts,vagas))
        DB.audit(i.guild_id,i.user.id,'criar operação',cur.lastrowid)
        await reply(i,f'Operação #{cur.lastrowid} criada para <t:{ts}:F>. Use /aviso para convocar. Um lembrete será enviado no início.')
    elif acao=='listar':
        rows=DB.rows("SELECT * FROM events WHERE g=? AND status='aberta' ORDER BY ts LIMIT 15",(i.guild_id,))
        await reply(i,'\n\n'.join(f"**#{r['id']} {r['title']}** • <t:{r['ts']}:f> • {r['capacity']} vagas\n{r['description'][:120]}" for r in rows) or 'Sem operações abertas.')
    else:
        e=DB.one('SELECT * FROM events WHERE g=? AND id=?',(i.guild_id,operacao))
        if not e: raise ValueError('Operação inexistente.')
        if acao=='entrar':
            DB.join(i.guild_id,i.user.id,operacao)
            await reply(i,'Inscrição confirmada.')
        elif acao=='sair':
            DB.execute('DELETE FROM attendance WHERE event=? AND u=?',(operacao,i.user.id))
            await reply(i,'Inscrição removida.')
        elif acao=='encerrar':
            DB.execute("UPDATE events SET status='encerrada' WHERE id=?",(operacao,))
            DB.audit(i.guild_id,i.user.id,'encerrar operação',operacao)
            await reply(i,'Operação encerrada.')
        else:
            rows=DB.rows('SELECT u FROM attendance WHERE event=?',(operacao,))
            await reply(i,'\n'.join(f"<@{r['u']}>" for r in rows) or 'Nenhum inscrito.',f"Inscritos • {e['title']}")

ticket_locks={}
async def open_ticket(i):
    cfg=await guard(i,member=False)
    await i.response.defer(ephemeral=True)
    key=(i.guild_id,i.user.id)
    async with ticket_locks.setdefault(key,asyncio.Lock()):
        r=DB.one('SELECT channel FROM tickets WHERE g=? AND u=?',key)
        if r:
            try: existing=await i.guild.fetch_channel(r['channel'])
            except discord.NotFound: existing=None
            if existing: return await reply(i,f'Seu atendimento: {existing.mention}')
        category=i.guild.get_channel(cfg.get('tickets',0))
        staff=i.guild.get_role(cfg.get('staff',0))
        if not isinstance(category,discord.CategoryChannel) or not staff: raise ValueError('Peça a um administrador para usar /configurar.')
        overwrites={i.guild.default_role:discord.PermissionOverwrite(view_channel=False),i.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,attach_files=True),staff:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),i.guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,manage_channels=True)}
        channel=await i.guild.create_text_channel(f'atendimento-{i.user.id}',category=category,overwrites=overwrites,topic=f'Atendimento de {i.user.id} • By Diaz')
        DB.execute('INSERT OR REPLACE INTO tickets VALUES(?,?,?)',(i.guild_id,i.user.id,channel.id))
        DB.audit(i.guild_id,i.user.id,'abrir ticket',channel.id)
        await channel.send(embed=embed('Atendimento privado',f'<@{i.user.id}>, descreva sua solicitação. A liderança pode encerrar com /ticket fechar.'))
        await reply(i,f'Ticket criado: {channel.mention}')

@bot.tree.command(name='ticket',description='Abrir atendimento ou fechar o ticket atual')
async def ticket(i:discord.Interaction,acao:Literal['abrir','fechar']):
    if acao=='abrir': return await open_ticket(i)
    await guard(i,staff=True)
    row=DB.one('SELECT * FROM tickets WHERE g=? AND channel=?',(i.guild_id,i.channel_id))
    if not row: raise ValueError('Use dentro de um ticket ativo.')
    await i.response.defer(ephemeral=True)
    text=[]
    async for m in i.channel.history(limit=2000,oldest_first=True):
        text.append(f'{m.created_at.isoformat()} | {m.author} ({m.author.id}) | {m.content}\n'+'\n'.join(a.url for a in m.attachments)+'\n'+'\n'.join(e.description or '' for e in m.embeds))
    cfg=DB.config(i.guild_id)
    logs=i.guild.get_channel(cfg.get('logs',0))
    if not logs: raise ValueError('Configure um canal de logs para receber a transcrição antes de fechar.')
    await logs.send(content=f'Transcrição de {i.channel.name} • primeiras 2.000 mensagens • By Diaz',file=discord.File(io.BytesIO('\n'.join(text).encode()),filename=f'ticket-{i.channel_id}.txt'))
    owner=await i.guild.fetch_member(row['u']) if i.guild.get_member(row['u']) else discord.Object(id=row['u'])
    # Mantém o canal como arquivo; não apaga mensagens.
    overwrite=discord.PermissionOverwrite(view_channel=True,send_messages=False,add_reactions=False)
    if isinstance(owner,discord.Member): await i.channel.set_permissions(owner,overwrite=overwrite)
    else:
        # fetch_member funciona sem intent privilegiado; um usuário ausente não pode escrever.
        try: await i.channel.set_permissions(await i.guild.fetch_member(row['u']),overwrite=overwrite)
        except discord.NotFound: pass
    await i.channel.edit(name=f'fechado-{i.channel_id}')
    DB.execute('DELETE FROM tickets WHERE g=? AND channel=?',(i.guild_id,i.channel_id))
    DB.audit(i.guild_id,i.user.id,'fechar ticket',i.channel_id)
    await reply(i,'Ticket arquivado. Transcrição enviada aos logs. O canal foi preservado.')

@bot.tree.command(name='aviso',description='Publicar comunicado da liderança sem menções em massa')
async def announcement(i:discord.Interaction,titulo:str,texto:str):
    cfg=await guard(i,staff=True)
    channel=i.guild.get_channel(cfg.get('announcements',0))
    if not channel: raise ValueError('Canal de avisos não configurado.')
    await channel.send(embed=embed(titulo[:200],texto))
    DB.audit(i.guild_id,i.user.id,'aviso',titulo)
    await reply(i,'Comunicado enviado.')

EXPORTS={
    'membros':('SELECT * FROM members WHERE g=?',()),
    'ponto':('SELECT * FROM shifts WHERE g=?',()),
    'caixa':("SELECT * FROM ledger WHERE g=? AND kind='caixa'",()),
    'estoque':("SELECT * FROM ledger WHERE g=? AND kind='estoque'",()),
    'entregas':('SELECT * FROM deliveries WHERE g=?',()),
    'auditoria':('SELECT * FROM audit WHERE g=?',()),
    'registros':('SELECT * FROM records WHERE g=?',()),
}

def csv_bytes(rows):
    out=io.StringIO()
    if rows:
        writer=csv.DictWriter(out,fieldnames=rows[0].keys(),delimiter=';')
        writer.writeheader()
        for row in rows:
            writer.writerow({k:("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return out.getvalue().encode('utf-8-sig')

@bot.tree.command(name='relatorio',description='Exportar relatórios CSV por módulo')
async def report(i:discord.Interaction,tipo:Literal['membros','ponto','caixa','estoque','entregas','auditoria','registros']):
    await guard(i,staff=True)
    await i.response.defer(ephemeral=True)
    rows=DB.rows(EXPORTS[tipo][0],(i.guild_id,))
    data=csv_bytes(rows)
    if len(data)>8*1024*1024: raise ValueError('Relatório acima de 8 MB. Exporte pelo backup local.')
    await reply(i,f'{len(rows)} registros. Horários no CSV são Unix UTC.',file=discord.File(io.BytesIO(data),filename=f'{tipo}-By-Diaz.csv'))
    DB.audit(i.guild_id,i.user.id,'exportar',tipo)

@bot.tree.command(name='backup',description='Gerar backup local do banco • Administrador')
@app_commands.default_permissions(administrator=True)
async def backup_cmd(i:discord.Interaction):
    await guard(i,admin=True)
    path=make_backup()
    DB.audit(i.guild_id,i.user.id,'backup',path.name)
    await reply(i,f'Backup salvo no computador/hospedagem: backups/{path.name}. O arquivo não contém o token.')

def make_backup():
    folder=Path('backups'); folder.mkdir(exist_ok=True)
    path=folder/f"faccao-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite3"
    DB.backup(path)
    for old in sorted(folder.glob('faccao-*.sqlite3'))[:-14]: old.unlink()
    return path

last_backup=0
@tasks.loop(seconds=60)
async def maintenance():
    global last_backup
    try:
        now=int(time.time())
        # Ponto esquecido é limitado a 12h, inclusive após reiniciar.
        with DB.tx():
            overdue=DB.rows('SELECT * FROM shifts WHERE end IS NULL AND start<?',(now-43200,))
            for shift in overdue:
                DB.execute('UPDATE shifts SET end=start+43200 WHERE id=?',(shift['id'],))
                DB.audit(shift['g'],0,'ponto encerrado automaticamente',shift['id'])
        for e in DB.rows("SELECT * FROM events WHERE status='aberta' AND reminded=0 AND ts<=?",(now,)):
            guild=bot.get_guild(e['g'])
            if not guild: continue
            cfg=DB.config(e['g']); channel=guild.get_channel(cfg.get('announcements',0))
            if not channel: continue
            if now-e['ts']>86400:
                DB.execute('UPDATE events SET reminded=1 WHERE id=?',(e['id'],)); continue
            try:
                await channel.send(embed=embed('Operação iniciando',f"**#{e['id']} {e['title']}**\n{e['description']}\nHorário: <t:{e['ts']}:F>\nConfira os participantes com /operacao participantes."))
                DB.execute('UPDATE events SET reminded=1 WHERE id=?',(e['id'],))
            except discord.HTTPException: log.warning('Falha no lembrete da operação %s',e['id'])
        if now-last_backup>86400:
            make_backup(); last_backup=now
    except Exception: log.exception('Falha na manutenção; nova tentativa em 60 segundos.')

@maintenance.before_loop
async def before_maintenance(): await bot.wait_until_ready()

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    token=os.getenv('DISCORD_TOKEN','')
    if not token or token=='COLE_O_TOKEN_AQUI' or not os.getenv('GUILD_ID','').isdigit():
        raise SystemExit('Configure DISCORD_TOKEN e GUILD_ID no arquivo .env. Leia o LEIA-ME.md.')
    bot.run(token,log_handler=None)
