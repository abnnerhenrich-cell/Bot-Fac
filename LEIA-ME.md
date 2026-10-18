# Central de Facção GTA RP — By Diaz

Bot de Discord em português para administrar uma facção **dentro do GTA RP**. Código aberto para personalizar. Python 3.11 ou superior; SQLite local; comandos slash; painel com botões persistentes; sem painel web e sem mensalidade de software. Precisa de computador ou hospedagem ligada e conectada para permanecer online.

## Comece aqui

1. Instale Python 3.11+ (no Windows marque **Add Python to PATH**).
2. Extraia o ZIP inteiro para uma pasta gravável.
3. Acesse https://discord.com/developers/applications, crie uma aplicação e abra **Bot**. Gere o token. **Não publique o token nem mande prints dele.**
4. Em **Bot → Privileged Gateway Intents**, ative **Message Content Intent**, necessário para transcrever o texto dos tickets. O bot não exige Server Members Intent.
5. Convide a aplicação pelo OAuth2 com os escopos `bot` e `applications.commands`. Permissões: Ver canais, Enviar mensagens, Inserir links, Anexar arquivos, Ler histórico, Gerenciar canais e Gerenciar cargos. Não é necessário dar Administrador ao bot.
6. No Discord, ative Modo desenvolvedor em Configurações → Avançado. Copie o ID do servidor.
7. Copie `.env.example` para `.env` e preencha `DISCORD_TOKEN` e `GUILD_ID`. Não use o segredo OAuth nem a chave pública no lugar do token.
8. Windows: execute `iniciar.bat`. Linux: execute `bash iniciar.sh`. Na primeira vez é preciso internet para instalar dependências. No Linux, se faltar venv, instale o pacote `python3-venv` da sua distribuição.
9. Crie cargos separados de **Liderança** e **Membro**, canais privados de **logs**, canal de **avisos** e categoria de **tickets**. Deixe o cargo do bot acima do cargo Membro.
10. Como administrador, execute `/configurar` e selecione os cargos/canais. Depois `/painel canal:#central`. Use `/membro cadastrar` para cadastrar os integrantes existentes.

Execução manual:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env antes de continuar
python bot.py
```

Os comandos são sincronizados apenas no servidor informado em `GUILD_ID`. Configure uma instância por servidor. Para atualizar sem perder registros, preserve `.env`, `data/` e `backups/`.

## Funções incluídas

| Módulo | Comandos / comportamento |
|---|---|
| Configuração | `/configurar`, `/painel`, `/ajuda`; nome da facção, cargos, canais e categoria |
| Recrutamento | Formulário no botão; nome do personagem, passaporte e disponibilidade; aprovação pela liderança |
| Membros | `/membro cadastrar`, `patente`, `desligar`; passaporte único, patente interna, concessão/remoção do cargo Membro |
| Perfil | `/perfil`; identidade RP, patente, horas e advertências; membro vê o próprio, liderança pode consultar outros |
| Ponto | Botões e `/ponto`; impede dois pontos abertos; persiste ao reiniciar; fecha automaticamente com 12 horas |
| Correção | `/ponto_corrigir`; liderança encerra ponto aberto informando duração total e motivo auditado |
| Ranking | `/ranking dias:7`; considera somente a parte das sessões dentro do período, incluindo sessões abertas |
| Produção | `/entrega` com comprovante opcional; só após aprovação entra no estoque e nas metas |
| Metas | `/meta`, `/metas`; objetivo por membro/item nos últimos sete dias, janela móvel |
| Estoque | `/estoque ver/entrada/saida`; quantidade inteira, saldo não negativo, histórico exportável |
| Caixa RP | `/caixa saldo/entrada/saida`; dinheiro fictício, valor inteiro em RP$, registro em centavos, saldo não negativo |
| Ausências | `/ausencia motivo retorno`; aprovação registrada; não altera automaticamente cargos nem metas |
| Advertências | `/advertencia aplicar/revogar`; motivo, autor e histórico; sem punições automáticas |
| Análise | `/registros` paginado e `/analisar`; recrutamentos, entregas e ausências; impede aprovação duplicada |
| Operações RP | `/operacao criar/listar/entrar/sair/participantes/encerrar`; agenda, descrição, vagas, inscrições e lembrete no início |
| Tickets | Botão ou `/ticket abrir`; canal privado por usuário; `/ticket fechar` arquiva e envia transcrição aos logs |
| Comunicados | `/aviso`; publicação no canal configurado; sem disparar menções em massa |
| Relatórios | `/relatorio`; CSV de membros, ponto, caixa, estoque, entregas, registros e auditoria |
| Backup | `/backup`; cópia SQLite consistente; também diária enquanto online; retenção das últimas 14 cópias |

## Exemplos

- `/membro cadastrar usuario:@Jogador nome:Pedro passaporte:123`
- `/membro patente usuario:@Jogador patente:Gerente`
- `/meta item:radio quantidade:20`
- `/entrega item:radio quantidade:5` → `/registros tipo:entrega` → `/analisar registro:1 decisao:aprovar`
- `/caixa acao:entrada valor:50000 motivo:Contribuição RP`
- `/operacao acao:criar titulo:Reunião data:25/12/2026 20:00 vagas:30 descricao:Reunião no QG`
- `/operacao acao:entrar operacao:1`
- `/ausencia motivo:Viagem retorno:30/12/2026`

As opções aparecem como campos separados no Discord. Datas usam Brasília (America/Sao_Paulo). Os horários exportados em CSV usam timestamp Unix; valores do caixa nos relatórios estão em centavos fictícios. IDs de Discord devem ser importados como texto em planilhas para preservar os dígitos.

## Permissões e comportamento

- Administradores e cargo Liderança usam comandos de gestão. Apenas administradores configuram o bot e geram backup manual.
- Demais usuários precisam de cadastro ativo no banco para usar os módulos internos. Recrutamento, ajuda e abertura de ticket ficam disponíveis aos visitantes.
- A patente é um campo interno: não concede cargos de liderança automaticamente.
- Desligar um membro inativa seu cadastro, fecha seu ponto e tenta retirar o cargo Membro. Cargos de liderança concedidos manualmente devem ser removidos manualmente pelo administrador.
- O bot bloqueia cargos administrativos como cargo Membro no assistente de configuração. Não dê permissões administrativas a esse cargo depois de configurar.
- Os canais de logs devem ser privados da liderança. Eles recebem cadastros, movimentações selecionadas e transcrições. A auditoria completa de mutações fica no SQLite e pode ser exportada.
- Dados financeiros e de estoque usam transações. Duas aprovações da mesma entrega não geram estoque duas vezes.
- O banco não deve ser editado enquanto o bot está ligado. Rode apenas uma instância por pasta/banco.
- As mensagens de botões persistem após reiniciar; a configuração é buscada no banco em cada uso.

## Tickets e limites conhecidos

O encerramento preserva o canal, bloqueia envio pelo autor e envia aos logs uma transcrição das primeiras 2.000 mensagens. Se falhar o envio da transcrição, o ticket não é encerrado. Mensagens além desse limite continuam no canal arquivado, mas não entram no arquivo. Anexos são registrados como URLs, que podem expirar; não são baixados. Servidores grandes precisam de rotina manual para remover canais arquivados após guardar os arquivos necessários. Administradores sempre podem acessar canais privados pelo sistema de permissões do Discord.

O bot não verifica presença dentro do GTA: ponto e entregas são declarados pelos usuários, com aprovação humana para entregas. Não há automação de jogo, sincronização de inventário FiveM, pagamentos reais ou conexão com vRP/QBCore/ESX. Isso exige a base, recursos e permissões do seu servidor. Operações são apenas eventos fictícios de RP no Discord.

Lembretes tentam novamente após falha de rede. Se o bot ficar offline, eventos atrasados em até 24h são lembrados quando voltar; os mais antigos não geram aviso. Em falha no instante entre enviar e salvar, um lembrete pode se repetir. O ponto aberto continua contando após reiniciar, limitado a 12 horas pela manutenção. Feche manualmente ao sair e corrija sessões esquecidas antes do fechamento automático.

## Backup e restauração

Backups ficam em `backups/` na máquina que executa o bot, não no Discord. Copie periodicamente para outro dispositivo, pois perder o disco também perde os backups locais. Cada backup inclui dados dos membros e transcrições não estão nele (ficam no canal de logs). O token está em `.env`, fora do banco.

Para restaurar: pare o bot, guarde uma cópia da pasta `data/`, substitua `data/faccao.sqlite3` por um backup e remova os arquivos antigos `faccao.sqlite3-wal` e `faccao.sqlite3-shm` **somente com o bot parado**. Reinicie. Se alterou `DATABASE_PATH`, use o caminho configurado.

## Problemas comuns

- **Comandos não aparecem:** confira `GUILD_ID`, escopo `applications.commands`, console e convite; reabra o Discord.
- **PrivilegedIntentsRequired:** ative Message Content Intent na página Bot do portal.
- **Token inválido:** redefina o token no portal e atualize `.env`; nunca compartilhe o token.
- **Não consegue dar cargo:** coloque o cargo do bot acima de Membro e conceda Gerenciar cargos.
- **Ticket não abre:** confira Gerenciar canais e a categoria configurada; o servidor pode ter atingido o limite de canais.
- **Transcrição vazia:** confira Message Content Intent e Ler histórico de mensagens; reinicie após mudar o intent.
- **SQLite readonly:** extraia para uma pasta gravável; não execute diretamente dentro do ZIP.
- **Não fica 24h online:** o processo precisa continuar rodando; o ZIP não inclui hospedagem.

## Testes e estrutura

```bash
python -m unittest discover -s tests -v
```

`bot.py`: comandos, interface e rotinas. `store.py`: banco e transações. `tests/`: testes das regras. `requirements.txt`: dependências fixadas. `iniciar.sh`/`iniciar.bat`: inicialização. Não envie `.env` ao publicar o projeto.

Validação entregue: testes locais de saldo/estoque, isolamento, aprovação única, conflitos de recrutamento, ponto, vagas e restauração; geração local dos esquemas dos comandos e persistência da interface. Conexão real e permissões precisam ser verificadas no seu servidor após inserir o token. Não foi feito login no Discord durante a criação.

Referências da implementação: https://discordpy.readthedocs.io/en/stable/interactions/api.html e https://discordpy.readthedocs.io/en/stable/api.html .

Créditos: **By Diaz**. Status: **Assistindo By Diaz**.
