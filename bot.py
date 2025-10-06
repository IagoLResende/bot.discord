import os
import discord
from discord.ext import commands
from discord.ui import View, button

# === CONFIGURAÇÃO DE INTENTS ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# === DICIONÁRIO PARA FILAS ===
filas = {}

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

# === FUNÇÃO DE ADIÇÃO À FILA ===
async def add_to_queue(interaction: discord.Interaction, dg_name: str, role: str):
    user = interaction.user
    queue = filas[dg_name]

    # Verifica se o usuário já está em alguma função
    if any(user in q for q in queue.values()):
        await interaction.response.send_message("⚠️ Você já está na fila!", ephemeral=True)
        return

    queue[role].append(user)
    await interaction.response.send_message(
        f"✅ Você entrou como **{role.upper()}** na DG **{dg_name}**!",
        ephemeral=True
    )

    # Verifica se a PT está completa
    if len(queue["tank"]) >= 1 and len(queue["healer"]) >= 1 and len(queue["dps"]) >= 4:
        tank = queue["tank"].pop(0)
        healer = queue["healer"].pop(0)
        dps = [queue["dps"].pop(0) for _ in range(4)]

        msg = (
            f"🎯 **PARTY FORMADA para {dg_name}!**\n"
            f"🛡️ {tank.mention}\n"
            f"💚 {healer.mention}\n"
            f"⚔️ {', '.join(p.mention for p in dps)}"
        )
        await interaction.channel.send(msg)

# === COMANDOS DO BOT ===
@bot.command()
async def criar_fila(ctx, dg_name: str):
    if dg_name in filas:
        await ctx.send(f"⚠️ Já existe uma fila ativa para **{dg_name}**.")
        return

    filas[dg_name] = {"tank": [], "healer": [], "dps": []}
    await ctx.send(
        f"🎮 **Fila criada para `{dg_name}`!** Clique para entrar:",
        view=PartyView(dg_name)
    )

@bot.command()
async def fila(ctx, dg_name: str = None):
    if not filas:
        await ctx.send("❌ Nenhuma fila ativa no momento.")
        return

    if dg_name:
        if dg_name not in filas:
            await ctx.send("⚠️ Essa DG não possui uma fila ativa.")
            return
        queues = {dg_name: filas[dg_name]}
    else:
        queues = filas

    for dg, queue in queues.items():
        e = discord.Embed(title=f"Fila Atual - {dg}", color=discord.Color.blurple())
        for k, v in queue.items():
            nomes = "\n".join(p.mention for p in v) or "Vazio"
            e.add_field(name=k.upper(), value=nomes, inline=False)
        await ctx.send(embed=e)

@bot.command()
async def remover(ctx):
    user = ctx.author
    removed = False

    for dg_name, queue in filas.items():
        for role, players in queue.items():
            if user in players:
                players.remove(user)
                await ctx.send(f"❌ {user.mention} foi removido da fila de **{role.upper()}** em **{dg_name}**.")
                removed = True
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
TOKEN = os.getenv("DISCORD_TOKEN")  # variável de ambiente segura
if not TOKEN:
    print("❌ ERRO: variavel DISCORD_TOKEN não configurada!")
else:
    bot.run(TOKEN)
