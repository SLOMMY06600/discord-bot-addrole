import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

load_dotenv()

OWNERS_FILE = "owners.json"
PERMS_FILE = "permissions.json"
LOGS_FILE = "logs.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
bot.remove_command("help")

AUTHORIZED_ROLE_IDS = list(map(int, os.getenv("AUTHORIZED_ROLE_IDS", "").split(","))) if os.getenv("AUTHORIZED_ROLE_IDS") else []
PROTECTED_ROLE_ID = int(os.getenv("PROTECTED_ROLE_ID", "0"))

DANGEROUS_PERM_NAMES = [
    "administrator", "ban_members", "kick_members", "manage_guild",
    "manage_channels", "manage_roles", "manage_webhooks",
    "mention_everyone", "manage_nicknames", "moderate_members",
]

def is_dangerous(role: discord.Role):
    perms = role.permissions
    for name in DANGEROUS_PERM_NAMES:
        if getattr(perms, name, False):
            return True
    return False

def load_perms():
    if not os.path.exists(PERMS_FILE):
        return {}
    with open(PERMS_FILE, "r") as f:
        data = json.load(f)
    for cmd, roles in data.items():
        if isinstance(roles, list):
            data[cmd] = {rid: "Inconnu" for rid in roles}
    return data

def save_perms(data):
    with open(PERMS_FILE, "w") as f:
        json.dump(data, f, indent=4)

cmd_perms = load_perms()

def load_logs():
    if not os.path.exists(LOGS_FILE):
        return {}
    with open(LOGS_FILE, "r") as f:
        return json.load(f)

def save_logs(data):
    with open(LOGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

logs_data = load_logs()

async def send_log(guild, log_type, message):
    guild_logs = logs_data.get(str(guild.id), {})
    channel_id = guild_logs.get(log_type)
    if channel_id:
        channel = guild.get_channel(int(channel_id))
        if channel:
            await channel.send(message)

VALID_CMDS = {"ban", "kick", "clear", "addrole", "delrole", "derank", "setperm", "unsetperm", "unban", "help", "config"}

def is_owner(user_id: int):
    if user_id == int(os.getenv("OWNER_ID", "0")):
        return True
    if not os.path.exists(OWNERS_FILE):
        return False
    with open(OWNERS_FILE, "r") as f:
        owners = json.load(f)
    return str(user_id) in owners

def can_use(ctx, cmd_name):
    if is_owner(ctx.author.id):
        return True
    if any(role.id in AUTHORIZED_ROLE_IDS for role in ctx.author.roles):
        return True
    allowed_roles = cmd_perms.get(cmd_name.lower(), {})
    return any(str(role.id) in allowed_roles for role in ctx.author.roles)

@bot.command()
async def addrole(ctx, member: discord.Member, role_id: int):
    if not can_use(ctx, "addrole"):
        return await ctx.send("Permission refusée")
    role = ctx.guild.get_role(role_id)
    if role is None:
        return await ctx.send("Rôle introuvable")
    if is_dangerous(role) and not is_owner(ctx.author.id):
        return await ctx.send("Ce rôle a des permissions élevées, impossible de l'ajouter")
    if role in member.roles:
        return await ctx.send(f"{member.name} a déjà le rôle {role.name}")
    await member.add_roles(role)
    await ctx.send(f"Rôle {role.name} ajouté à {member.name}")
    await send_log(ctx.guild, "addrole", f"`{ctx.author.name}` a ajouté le rôle `{role.name}` à `{member.name}`")

@bot.command()
async def delrole(ctx, member: discord.Member, role_id: int):
    if not can_use(ctx, "delrole"):
        return await ctx.send("Permission refusée")
    role = ctx.guild.get_role(role_id)
    if role is None:
        return await ctx.send("Rôle introuvable")
    if is_dangerous(role) and not is_owner(ctx.author.id):
        return await ctx.send("Ce rôle a des permissions élevées, impossible de le retirer")
    if role not in member.roles:
        return await ctx.send(f"{member.name} n'a pas le rôle {role.name}")
    await member.remove_roles(role)
    await ctx.send(f"Rôle {role.name} retiré de {member.name}")
    await send_log(ctx.guild, "delrole", f"`{ctx.author.name}` a retiré le rôle `{role.name}` de `{member.name}`")

@bot.command()
async def derank(ctx, member: discord.Member):
    if not can_use(ctx, "derank"):
        return await ctx.send("Permission refusée")
    roles_to_remove = [role for role in member.roles if role.id != PROTECTED_ROLE_ID and role != ctx.guild.default_role]
    await member.remove_roles(*roles_to_remove)
    await ctx.send(f"Tous les rôles retirés de {member.name}")

@bot.command()
async def ban(ctx, member: discord.Member, *, reason=None):
    if not can_use(ctx, "ban"):
        return await ctx.send("Permission refusée")
    await member.ban(reason=reason)
    await ctx.send(f"{member.name} a été banni")

@bot.command()
async def kick(ctx, member: discord.Member, *, reason=None):
    if not can_use(ctx, "kick"):
        return await ctx.send("Permission refusée")
    await member.kick(reason=reason)
    await ctx.send(f"{member.name} a été expulsé")

@bot.command()
async def clear(ctx, amount: int):
    if not can_use(ctx, "clear"):
        return await ctx.send("Permission refusée")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"{len(deleted) - 1} messages supprimés", delete_after=5)

@bot.command()
async def unban(ctx, user_id: int):
    if not can_use(ctx, "unban"):
        return await ctx.send("Permission refusée")
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user)
    await ctx.send(f"{user.name} a été débanni")

@bot.command()
async def setperm(ctx, perm_name: str, role: discord.Role):
    if not can_use(ctx, "setperm") and not can_use(ctx, "config"):
        return await ctx.send("Permission refusée")
    if perm_name.lower() not in VALID_CMDS:
        return await ctx.send(f"Commande inconnue. Disponibles: {', '.join(VALID_CMDS)}")
    perms = cmd_perms.setdefault(perm_name.lower(), {})
    if str(role.id) not in perms:
        perms[str(role.id)] = role.name
        save_perms(cmd_perms)
    await ctx.send(f"Le rôle {role.name} peut maintenant utiliser !{perm_name}")
    await send_log(ctx.guild, "setperm", f"`{ctx.author.name}` a donné la permission `!{perm_name}` au rôle `{role.name}`")

@bot.command()
async def unsetperm(ctx, perm_name: str, role: discord.Role):
    if not can_use(ctx, "unsetperm") and not can_use(ctx, "config"):
        return await ctx.send("Permission refusée")
    if perm_name.lower() not in VALID_CMDS:
        return await ctx.send(f"Commande inconnue. Disponibles: {', '.join(VALID_CMDS)}")
    perms = cmd_perms.get(perm_name.lower(), {})
    if str(role.id) in perms:
        del perms[str(role.id)]
        save_perms(cmd_perms)
    await ctx.send(f"Le rôle {role.name} ne peut plus utiliser !{perm_name}")

@bot.command()
async def autologs(ctx):
    if not is_owner(ctx.author.id):
        return await ctx.send("Permission refusée")
    guild = ctx.guild
    category = discord.utils.get(guild.categories, name="LOGS")
    if category is None:
        category = await guild.create_category("LOGS")
    channels = {}
    for name in ["addrole", "delrole", "setperm"]:
        ch_name = f"🔒・{name}-logs"
        ch = discord.utils.get(category.channels, name=ch_name)
        if ch is None:
            ch = await guild.create_text_channel(ch_name, category=category)
        channels[name] = str(ch.id)
    logs_data[str(guild.id)] = channels
    save_logs(logs_data)
    await ctx.send("Salons de logs créés dans la catégorie LOGS")

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__()

    @discord.ui.select(
        placeholder="Choisir une catégorie",
        options=[
            discord.SelectOption(label="Serveur Gestion", value="main"),
            discord.SelectOption(label="Modération", value="mod"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        if choice == "main":
            embed = discord.Embed(
                title="Serveur Gestion",
                description="Gestion des rôles du serveur",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            embed.add_field(name="!addrole @user role_id", value="Ajoute un rôle", inline=False)
            embed.add_field(name="!delrole @user role_id", value="Retire un rôle", inline=False)
            embed.add_field(name="!setperm commande @role", value="Donne une permission à un rôle", inline=False)
            embed.add_field(name="!unsetperm commande @role", value="Retire une permission à un rôle", inline=False)
            embed.add_field(name="!autologs", value="Crée les salons de logs", inline=False)
        elif choice == "mod":
            embed = discord.Embed(
                title="Modération",
                description="Commandes de modération",
                color=discord.Color.from_rgb(0, 0, 0)
            )
            embed.add_field(name="!ban @user", value="Bannit un membre", inline=False)
            embed.add_field(name="!kick @user", value="Expulse un membre", inline=False)
            embed.add_field(name="!clear 10", value="Supprime des messages", inline=False)
            embed.add_field(name="!unban user_id", value="Débannit un membre", inline=False)
            embed.add_field(name="!derank @user", value="Retire tous les rôles", inline=False)
        else:
            embed = discord.Embed(
                title="Erreur",
                description="Catégorie inconnue",
                color=discord.Color.from_rgb(0, 0, 0)
            )
        await interaction.response.edit_message(embed=embed, view=self)

@bot.command()
async def help(ctx):
    if ctx.author.id != 1425562222251479222:
        allowed = cmd_perms.get("help", {})
        if not any(str(role.id) in allowed for role in ctx.author.roles):
            return await ctx.send("Permission refusée")
    embed = discord.Embed(
        title="Menu d'aide",
        description="Sélectionne une catégorie",
        color=discord.Color.from_rgb(0, 0, 0)
    )
    await ctx.send(embed=embed, view=HelpView())

bot.run(os.getenv("DISCORD_TOKEN"))
