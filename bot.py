from keep_alive import keep_alive
keep_alive()

import os
import discord
from discord.ext import commands
from discord.ui import View, button
import asyncio

# === CONFIGURAÇÃO DE INTENTS ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# === DICIONÁRIO PARA FILAS ===
# Estrutura: {dg_name: {"queue": {"tank": [], "healer": [], "dps": []}, "message": discord.Message, "task": asyncio.Task}}
filas = {}

# === TEMPO PARA EXPIRAR FILA (em segundos) ===
TEMPO_EXPIRAR = 3600  # 1 hora, você pode mudar

# === FUNÇÕES/EMOJIS/LIMITES POR FUNÇÃO ===
FUNCOES = {
    "tank": {"emoji": "🛡️", "limite": 1, "color": discord.Color.blue()},
    "healer": {"emoji": "💚", "limite": 1, "color": discord.Color.green()},
    "dps": {"emoji": "⚔️", "limite": 4, "color": discord.Color.red()}
}

# === CLASSE DE BOTÕES ===
class PartyView(View):
    def __init__(self, dg_name):
        super().__init__(timeout=None)
        self.dg_name = dg_name

    @button(label="🛡️ Tank", style=discord.ButtonStyle.primary)
    async def tank(self, interaction, button):
        await add_to_queue(interaction, self.dg_name, "tank")

    @button(label="💚 Healer", style=discord.ButtonStyle.success)
    async def healer(self, interaction, button):
        await add_to_queue(interaction, self.dg_name, "healer")

    @button(label="⚔️ DPS", style=discord.ButtonStyle.danger)
    async def dps(self, interaction, button):
        await add_to_queue(interaction, self.dg_name, "dps")

# === FUNÇÃO PARA CRIAR EMBED COM VAGAS RESTANTES E CORES ===
def criar_embed(queue, dg_name):
    e = discord.Embed(title=f"Fila Atual - {dg_name}", color=discord.Color.dark_gold())
    
    for role, players in queue.items():
        info = FUNCOES[role]
        emoji = info["emoji"]
        limite = info["limite"]
        restantes = limite - len(players)
        nomes = "\n".join(p.mention for p in players) or "Vazio"
        e.add_field(
            name=f"{emoji} {role.upper()} - Vagas restantes: {restantes}",
            value=nomes,
            inline=False
        )
    return e

# === FUNÇÃO DE ADIÇÃO À FILA ===
async def add_to_queue(interaction: discord.Interaction, dg_name: str, role: str):
    user = interaction.user
    fila_info = filas[dg_name]
    queue = fila_info["queue"]
    limite = FUNCOES[role]["limite"]

    # Verifica se o usuário já está em alguma função
    if any(user in q for q in queue.values()):
        await interaction.response.send_message("⚠️ Você já está na fila!", ephemeral=True)
        return

    # Verifica se já atingiu limite da função
    if len(queue[role]) >= limite:
        await interaction.response.send_message(f"⚠️ A função {role.upper()} já está cheia!", ephemeral=True)
        return

    queue[role].append(user)
    await interaction.response.send_message(
        f"✅ Você entrou como **{role.upper()}** na DG **{dg_name}**!",
        ephemeral=True
    )

    # Atualiza embed
    await fila_info["message"].edit(embed=criar_embed(queue, dg_name), view=PartyView(dg_name))

    # Verifica se a party está completa
    if all(len(queue[r]) >= FUNCOES[r]["limite"] for r in queue):
        tank = queue["tank"].pop(0)
        healer = queue["healer"].pop(0)
        dps = [queue["dps"].pop(0) for _ in range(FUNCOES["dps"]["limite"])]

        msg = (
            f"🎯 **PARTY FORMADA para {dg_name}!**\n"
            f"{FUNCOES['tank']['emoji']} {tank.mention}\n"
            f"{FUNCOES['healer']['emoji']} {healer.mention}\n"
            f"{FUNCOES['dps']['emoji']} {', '.join(p.mention for p in dps)}"
        )
        await interaction.channel.send(msg)

        # Atualiza novamente embed
        await fila_info["message"].edit(embed=criar_embed(queue, dg_name), view=PartyView(dg_name))

# === COMANDOS DO BOT ===
@bot.command()
async def criar_fila(ctx, dg_name: str):
    if dg_name in filas:
        await ctx.send(f"⚠️ Já existe uma fila ativa para **{dg_name}**.")
        return

    queue = {role: [] for role in FUNCOES}
    embed = criar_embed(queue, dg_name)
    msg = await ctx.send(
        f"🎮 **Fila criada para `{dg_name}`! Clique nos botões para entrar:**",
        embed=embed,
        view=PartyView(dg_name)
    )

    filas[dg_name] = {"queue": queue, "message": msg, "task": None}
    filas[dg_name]["task"] = asyncio.create_task(expirar_fila(dg_name, TEMPO_EXPIRAR))

async def expirar_fila(dg_name, delay):
    await asyncio.sleep(delay)
    if dg_name in filas:
        await filas[dg_name]["message"].channel.send(f"⏰ A fila de **{dg_name}** expirou e foi removida automaticamente.")
        del filas[dg_name]

@bot.command()
async def excluir_fila(ctx, dg_name: str):
    if dg_name not in filas:
        await ctx.send("⚠️ Essa fila não existe.")
        return
    await filas[dg_name]["message"].channel.send(f"❌ A fila de **{dg_name}** foi excluída manualmente.")
    if filas[dg_name]["task"]:
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
                removed = True
                await fila_info["message"].edit(embed=criar_embed(queue, dg_name), view=PartyView(dg_name))
                break
        if removed:
            break

    if not removed:
        await ctx.send("⚠️ Você não está em nenhuma fila.")

# === EVENTO DE STATUS E LOG ===
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    await bot.change_presence(activity=discord.Game("Gerenciando filas 🏰"))

# === EXECUÇÃO DO BOT ===
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ ERRO: variavel DISCORD_TOKEN não configurada!")
else:
    bot.run(TOKEN)
