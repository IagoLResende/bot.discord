import os
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import asyncio

# Obtém o token diretamente da variável de ambiente do Railway
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("⚠️ Variável DISCORD_TOKEN não definida no Railway!")

# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Estruturas
filas = {}  # {dg_name: {"queue": {"tank": [], "healer": [], "dps": []}, "message": discord.Message, "task": asyncio.Task}}
TEMPO_EXPIRAR = 3600  # 1 hora

FUNCOES = {
    "tank": {"emoji": "🛡️", "limite": 1, "color": discord.Color.blue()},
    "healer": {"emoji": "💚", "limite": 1, "color": discord.Color.green()},
    "dps": {"emoji": "⚔️", "limite": 4, "color": discord.Color.red()}
}

# Cria embed da fila
def criar_embed(queue, dg_name):
    embed = discord.Embed(title=f"Fila Atual - {dg_name}", color=discord.Color.gold())
    for role, players in queue.items():
        restantes = FUNCOES[role]["limite"] - len(players)
        nomes = "\n".join(p.mention for p in players) if players else "Vazio"
        embed.add_field(name=f"{FUNCOES[role]['emoji']} {role.upper()} - Vagas restantes: {restantes}", value=nomes, inline=False)
    return embed

# Classe para os botões
class PartyView(View):
    def __init__(self, dg_name):
        super().__init__(timeout=None)
        self.dg_name = dg_name

    @discord.ui.button(label="🛡️ Tank", style=discord.ButtonStyle.primary)
    async def tank(self, interaction: discord.Interaction, button: Button):
        await add_to_queue(interaction, self.dg_name, "tank")

    @discord.ui.button(label="💚 Healer", style=discord.ButtonStyle.success)
    async def healer(self, interaction: discord.Interaction, button: Button):
        await add_to_queue(interaction, self.dg_name, "healer")

    @discord.ui.button(label="⚔️ DPS", style=discord.ButtonStyle.danger)
    async def dps(self, interaction: discord.Interaction, button: Button):
        await add_to_queue(interaction, self.dg_name, "dps")

# Adiciona usuário à fila
async def add_to_queue(interaction, dg_name, role):
    user = interaction.user
    fila_info = filas[dg_name]
    queue = fila_info["queue"]

    if any(user in q for q in queue.values()):
        await interaction.response.send_message("⚠️ Você já está na fila!", ephemeral=True)
        return

    if len(queue[role]) >= FUNCOES[role]["limite"]:
        await interaction.response.send_message(f"⚠️ A função {role.upper()} já está cheia!", ephemeral=True)
        return

    queue[role].append(user)
    await interaction.response.send_message(f"✅ Você entrou como **{role.upper()}** na DG **{dg_name}**!", ephemeral=True)

    await fila_info["message"].edit(embed=criar_embed(queue, dg_name), view=PartyView(dg_name))

    # Verifica se a party está completa
    if all(len(queue[r]) >= FUNCOES[r]["limite"] for r in queue):
        tank = queue["tank"].pop(0)
        healer = queue["healer"].pop(0)
        dps = [queue["dps"].pop(0) for _ in range(FUNCOES["dps"]["limite"])]

        msg = f"🎯 **PARTY FORMADA para {dg_name}!**\n{FUNCOES['tank']['emoji']} {tank.mention}\n{FUNCOES['healer']['emoji']} {healer.mention}\n{FUNCOES['dps']['emoji']} {', '.join(p.mention for p in dps)}"
        await interaction.channel.send(msg)

        await fila_info["message"].edit(embed=criar_embed(queue, dg_name), view=PartyView(dg_name))

# Expira fila automaticamente
async def expirar_fila(dg_name, delay):
    await asyncio.sleep(delay)
    if dg_name in filas:
        await filas[dg_name]["message"].channel.send(f"⏰ A fila de **{dg_name}** expirou e foi removida automaticamente.")
        del filas[dg_name]

# Comandos do bot
@bot.command()
async def criar_fila(ctx, dg_name: str):
    if dg_name in filas:
        await ctx.send(f"⚠️ Já existe uma fila ativa para **{dg_name}**.")
        return

    queue = {role: [] for role in FUNCOES}
    embed = criar_embed(queue, dg_name)
    msg = await ctx.send(f"🎮 **Fila criada para `{dg_name}`! Clique nos botões para entrar:**", embed=embed, view=PartyView(dg_name))

    task = asyncio.create_task(expirar_fila(dg_name, TEMPO_EXPIRAR))
    filas[dg_name] = {"queue": queue, "message": msg, "task": task}

@bot.command()
async def excluir_fila(ctx, dg_name: str):
    if dg_name not in filas:
        await ctx.send("⚠️ Essa fila não existe.")
        return
    await filas[dg_name]["message"].channel.send(f"❌ A fila de **{dg_name}** foi excluída manualmente.")
    filas[dg_name]["task"].cancel()
    del filas[dg_name]

@bot.command()
async def remover(ctx):
    user = ctx.author
    removed = False
    for dg_name, fila_info in filas.items():
        queue = fila_info["queue"]
        for role, players in queue.items():
            if user in players:
                players.remove(user)
                await ctx.send(f"❌ {user.mention} foi removido da fila de **{role.upper()}** em **{dg_name}**.")
                await fila_info["message"].edit(embed=criar_embed(queue, dg_name), view=PartyView(dg_name))
                removed = True
                break
        if removed:
            break
    if not removed:
        await ctx.send("⚠️ Você não está em nenhuma fila.")

@bot.command()
async def fila(ctx):
    if not filas:
        await ctx.send("⚠️ Não há filas ativas no momento.")
        return

    embed = discord.Embed(title="🎮 Filas Ativas", color=discord.Color.gold())
    for dg_name, fila_info in filas.items():
        queue = fila_info["queue"]
        status = ""
        for role, players in queue.items():
            restantes = FUNCOES[role]["limite"] - len(players)
            status += f"{FUNCOES[role]['emoji']} {role.upper()}: {len(players)}/{FUNCOES[role]['limite']} ({restantes} vagas restantes)\n"
        embed.add_field(name=dg_name, value=status, inline=False)
    await ctx.send(embed=embed)

# Evento ready
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Game("Gerenciando filas 🏰"))

# Executa o bot
bot.run(TOKEN)
