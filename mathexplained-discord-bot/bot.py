import asyncio
import io
import os
import ssl
import socket
from datetime import datetime
import aiohttp
import certifi
import discord
from discord import app_commands
from dotenv import load_dotenv
import moderation
import problems # internal import
import duelstats # internal import
import math_render # internal import

load_dotenv('.env')
_ssl_context = ssl.create_default_context(cafile=certifi.where())
BRAND_COLOR = discord.Color.og_blurple()

CATEGORY_LABELS = {
    problems.CATEGORY_ALGEBRA: "Algebra",
    problems.CATEGORY_GEOMETRY: "Geometry",
    problems.CATEGORY_COMBINATORICS: "Combinatorics",
    problems.CATEGORY_NUMBERTHEORY: "Number Theory",
    problems.CATEGORY_ADVANCED: "Advanced",
}
CATEGORY_CHOICES = [
    app_commands.Choice(name=label, value=code)
    for code, label in CATEGORY_LABELS.items()
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MathEXplainedBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.spam_tracker = moderation.SpamTracker()

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        self.http.connector = aiohttp.TCPConnector(
            limit=0, family=socket.AF_INET, ssl=_ssl_context
        )
        await super().start(token, reconnect=reconnect)

    async def setup_hook(self):
        moderation.init_db()
        problems.init_db()
        duelstats.init_db()
        synced = await self.tree.sync()
        print(f"Synced {len(synced)} commands")

bot = MathEXplainedBot()

# --- commands and events --- #

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    duel = active_duels.get(message.channel.id)
    if duel is not None:
        await duel.on_message(message)

    if bot.spam_tracker.record_and_check(message.author.id):
        member = message.author
        reason = (
            f"Sent {moderation.SPAM_MESSAGE_COUNT} messages within "
            f"{moderation.SPAM_WINDOW_SECONDS}s (spam flood)"
        )

        # DM the user (before kicking, while we still share a server) with a
        # fresh invite so they can rejoin. A kick — unlike a ban — doesn't block
        # re-entry, but their original invite may be gone, so we mint a new one.
        invite_url = await _make_rejoin_invite(message.channel)
        await _dm_kick_notice(member, message.guild, invite_url)

        try:
            await message.guild.kick(member, reason=reason)
        except discord.Forbidden:
            await message.channel.send(
                f"⚠️ Detected spam from {member.mention} but I lack permission to kick them."
            )
        else:
            # Only log an offense when the member was actually kicked.
            moderation.log_offense(
                user_id=member.id,
                user_name=str(member),
                guild_id=message.guild.id,
                reason=reason,
                action="kick",
            )
            await message.channel.send(f"🚫 Kicked {member.mention} for spamming.")

async def _make_rejoin_invite(channel):
    try:
        invite = await channel.create_invite(
            max_age=86400,   # valid for 24 hours
            max_uses=1,      # one rejoin
            unique=True,
            reason="Rejoin link for spam-kicked user",
        )
        return invite.url
    except discord.HTTPException:
        return None

async def _dm_kick_notice(member, guild, invite_url):
    embed = discord.Embed(
        title=f"You were removed from {guild.name}",
        description=(
            "You were automatically kicked for sending messages too quickly "
            "(spam flood). This isn't a ban — you're welcome to rejoin and keep "
            "chatting, just a bit more slowly. 😊"
        ),
        color=discord.Color.orange(),
    )
    if invite_url:
        embed.add_field(name="Rejoin link", value=invite_url, inline=False)
        embed.set_footer(text="This invite is valid for 24 hours.")
    try:
        await member.send(embed=embed)
    except discord.HTTPException:
        pass


@bot.tree.command(name="ping", description="View the bot's latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)} ms")


@bot.tree.command(name="offenses", description="View a user's moderation history")
@app_commands.default_permissions(kick_members=True)
@app_commands.checks.has_permissions(kick_members=True)
async def offenses(interaction: discord.Interaction, user: discord.Member):
    rows = moderation.get_offenses(user.id, interaction.guild_id)
    if not rows:
        await interaction.response.send_message(f"{user.mention} has no logged offenses.")
        return
    lines = []
    for reason, action, created_at in rows:
        ts = discord.utils.format_dt(datetime.fromtimestamp(created_at), style="f")
        entry = f"**{action.upper()}** — {reason} ({ts})"
        lines.append(entry)

    embed = discord.Embed(
        title=f"Offenses for {user}",
        description="\n".join(lines),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="renderlatex", description="Render a LaTeX expression as an image")
@app_commands.describe(latex="The LaTeX expression to render (e.g. \\int_0^1 x^2\\,dx)")
async def renderlatex(interaction: discord.Interaction, latex: str):
    await interaction.response.defer(thinking=True)
    try:
        png = await math_render.render_latex(latex)
    except math_render.RenderError as exc:
        await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
        return
    file = discord.File(io.BytesIO(png), filename="latex.png")
    await interaction.followup.send(file=file)


@bot.tree.command(name="renderasy", description="Render an Asymptote expression as an image")
@app_commands.describe(source="The Asymptote source code to render")
async def renderasy(interaction: discord.Interaction, source: str):
    '''
    await interaction.response.defer(thinking=True)
    try:
        png = await math_render.render_asymptote(source)
    except math_render.RenderError as exc:
        await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
        return
    if png is None:
        await interaction.followup.send(
            "⚠️ Asymptote is not installed on my system, so I can't render this right now.",
            ephemeral=True,
        )
        return
    file = discord.File(io.BytesIO(png), filename="asymptote.png")
    await interaction.followup.send(file=file)
    '''
    await interaction.response.send_message("🤫 This command is not ready yet!", ephemeral=True)
    # WEBMASTER_TODO: install Asymptote, uncomment, and test

async def _render_problem_images(prompt: str, answer: str | None):
    try:
        prompt_png = await math_render.render_latex(prompt)
        problem_file = discord.File(io.BytesIO(prompt_png), filename="problem.png")
        answer_file = None
        if answer:
            answer_png = await math_render.render_latex(answer)
            answer_file = discord.File(io.BytesIO(answer_png), filename="SPOILER_answer.png")
    except math_render.RenderError as exc:
        return None, None, str(exc)
    return problem_file, answer_file, None

async def _present_public_problem(interaction, title, prompt, answer, difficulty, 
                                  latex, image_url, submitted_by):
    diff = f" • Difficulty {difficulty}/10" if difficulty else ""
    author = f" • Submitted by {submitted_by}" if submitted_by else ""

    if latex:
        await interaction.response.defer(thinking=True)
        problem_file, answer_file, err = await _render_problem_images(prompt, answer)
        if err:
            await interaction.followup.send(f"⚠️ Couldn't render this problem: {err}", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"{title}{diff}",
            description="Answer is spoilered in the next message 👇" if answer_file else None,
            color=BRAND_COLOR,
        )
        embed.set_footer(text=f"MathEXplained{author}")
        await interaction.followup.send(embed=embed, file=problem_file)
        if answer_file:
            await interaction.followup.send(file=answer_file)
    else:
        embed = discord.Embed(
            title=f"{title}{diff}",
            description=prompt,
            color=BRAND_COLOR,
        )
        if answer:
            embed.add_field(name="Answer", value=f"||{answer}||", inline=False)
        if image_url:
            embed.set_image(url=image_url)
        embed.set_footer(text=f"MathEXplained{author}")
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="randproblem", description="View a random math problem")
@app_commands.describe(category="Which category to draw a problem from")
@app_commands.choices(category=CATEGORY_CHOICES)
async def randproblem(interaction: discord.Interaction, category: app_commands.Choice[str]):
    row = problems.get_random_problem(category.value)
    if row is None:
        await interaction.response.send_message(
            f"No approved **{category.name}** problems yet — be the first to `/submitproblem`!",
            ephemeral=True,
        )
        return

    _id, prompt, answer, difficulty, latex, image_url, submitted_by = row
    await _present_public_problem(
        interaction, f"{category.name} Problem", prompt, answer, difficulty,
        latex, image_url, submitted_by,
    )


@bot.tree.command(name="problem", description="View a specific problem by its ID")
@app_commands.describe(problem_id="The ID of the problem to view")
async def problem(interaction: discord.Interaction, problem_id: int):
    row = problems.get_problem(problem_id)
    if row is None or not row[8]:  # if problem not found or not approved
        await interaction.response.send_message(
            f"No approved problem found with ID `{problem_id}`.", ephemeral=True
        )
        return
    (_id, category, prompt, answer, difficulty, latex, image_url,
     submitted_by, _approved, _created) = row
    label = CATEGORY_LABELS.get(category, category)
    await _present_public_problem(
        interaction, f"{label} Problem #{_id}", prompt, answer, difficulty,
        latex, image_url, submitted_by,
    )


@bot.tree.command(name="submitproblem", description="Submit a math problem for others to view")
@app_commands.describe(
    category="Problem category",
    difficulty="Difficulty from 1 (easy) to 10 (hard)",
    problem="The problem statement",
    answer="The answer to the problem",
    latex="On: render problem & answer as LaTeX images; Off: plain text.",
    image="Optional image to attach to the problem",
)
@app_commands.choices(category=CATEGORY_CHOICES)
async def submitproblem(
    interaction: discord.Interaction,
    category: app_commands.Choice[str],
    difficulty: app_commands.Range[int, 1, 10],
    problem: str,
    answer: str,
    latex: bool,
    image: discord.Attachment | None = None,
):
    image_url = image.url if image else None
    new_id = problems.submit_problem(
        category=category.value,
        prompt=problem,
        answer=answer,
        difficulty=difficulty,
        latex=latex,
        image_url=image_url,
        submitted_by_id=interaction.user.id,
        submitted_by_name=str(interaction.user),
    )

    confirm = discord.Embed(
        title="✅ Problem submitted for review",
        description=(
            f"Your **{category.name}** problem (difficulty {difficulty}/10) is now pending "
            f"moderator approval. Submission ID `#{new_id}`."
        ),
        color=discord.Color.green(),
    )

    if latex:
        await interaction.response.defer(ephemeral=True, thinking=True)
        problem_file, answer_file, err = await _render_problem_images(problem, answer)
        if err:
            confirm.add_field(
                name="⚠️ LaTeX preview failed",
                value=f"The problem was saved, but rendering failed: {err}",
                inline=False,
            )
            await interaction.followup.send(embed=confirm, ephemeral=True)
        else:
            await interaction.followup.send(embed=confirm, file=problem_file, ephemeral=True)
            if answer_file:
                await interaction.followup.send(file=answer_file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=confirm, ephemeral=True)

def _pending_embed(row, index, total):
    (_id, category, prompt, answer, difficulty, latex, image_url,
     submitted_by, created_at) = row
    label = CATEGORY_LABELS.get(category, category)
    embed = discord.Embed(
        title=f"Pending #{_id} — {label}",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Problem", value=prompt[:1024] or "—", inline=False)
    embed.add_field(name="Answer", value=(answer or "—")[:1024], inline=False)
    embed.add_field(name="Difficulty", value=str(difficulty or "—"), inline=True)
    embed.add_field(name="LaTeX", value="On" if latex else "Off", inline=True)
    if image_url:
        embed.set_image(url=image_url)
    footer = f"Review {index + 1} of {total}"
    if submitted_by:
        footer += f" • Submitted by {submitted_by}"
    embed.set_footer(text=footer)
    return embed

# Valid category codes keyed by lowercase name/alias, for parsing the modal's free-text field.
_CATEGORY_ALIASES = {}
for _code, _label in CATEGORY_LABELS.items():
    _CATEGORY_ALIASES[_code.lower()] = _code
    _CATEGORY_ALIASES[_label.lower()] = _code
    _CATEGORY_ALIASES[_label.lower().replace(" ", "")] = _code

class EditProblemModal(discord.ui.Modal, title="Edit problem"):
    def __init__(self, row, on_saved=None):
        super().__init__()
        self._id = row[0]
        self._on_saved = on_saved
        self.category_in = discord.ui.TextInput(
            label="Category (algebra/geometry/…)", default=CATEGORY_LABELS.get(row[1], row[1]),
            max_length=20,
        )
        self.prompt_in = discord.ui.TextInput(
            label="Problem", style=discord.TextStyle.paragraph,
            default=row[2] or "", required=True, max_length=2000,
        )
        self.answer_in = discord.ui.TextInput(
            label="Answer", style=discord.TextStyle.paragraph,
            default=row[3] or "", required=True, max_length=1000,
        )
        self.difficulty_in = discord.ui.TextInput(
            label="Difficulty (1-10)", default=str(row[4] or ""),
            required=True, max_length=2,
        )
        self.latex_in = discord.ui.TextInput(
            label="LaTeX rendering? (on/off)", default="on" if row[5] else "off",
            required=True, max_length=3,
        )
        self.add_item(self.category_in)
        self.add_item(self.prompt_in)
        self.add_item(self.answer_in)
        self.add_item(self.difficulty_in)
        self.add_item(self.latex_in)

    async def on_submit(self, interaction: discord.Interaction):
        difficulty = None
        raw = self.difficulty_in.value.strip()
        if raw:
            if not raw.isdigit() or not (1 <= int(raw) <= 10):
                await interaction.response.send_message(
                    "⚠️ Difficulty must be a number from 1 to 10. No changes saved.",
                    ephemeral=True,
                )
                return
            difficulty = int(raw)

        category = _CATEGORY_ALIASES.get(self.category_in.value.strip().lower())
        if category is None:
            await interaction.response.send_message(
                "⚠️ Category must be one of: algebra, geometry, combinatorics, "
                "number theory, advanced. No changes saved.",
                ephemeral=True,
            )
            return

        latex = 1 if self.latex_in.value.strip().lower() in ("on", "yes", "true", "1") else 0

        problems.update_problem(
            self._id,
            category=category,
            prompt=self.prompt_in.value,
            answer=self.answer_in.value,
            difficulty=difficulty,
            latex=latex,
        )
        note = f"✏️ Saved edits to #{self._id}."
        if self._on_saved is not None:
            await self._on_saved(interaction, note)
        else:
            await interaction.response.send_message(note, ephemeral=True)

class ReviewView(discord.ui.View):
    def __init__(self, reviewer_id):
        super().__init__(timeout=300)
        self.reviewer_id = reviewer_id
        self.rows = problems.get_pending_submissions()
        self.index = 0

    def current_row(self):
        if 0 <= self.index < len(self.rows):
            return self.rows[self.index]
        return None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.reviewer_id:
            await interaction.response.send_message(
                "This review session isn't yours — run `/reviewproblem` yourself.",
                ephemeral=True,
            )
            return False
        return True

    def _render(self, note=None):
        """Returns (content, embed) for the current state."""
        row = self.current_row()
        if row is None:
            for child in self.children:
                child.disabled = True
            content = note or ""
            content += "\n🙈 No more pending problems to review." if content else \
                "🙈 No pending problems to review."
            return content.strip(), None
        return (note or None), _pending_embed(row, self.index, len(self.rows))

    async def _refresh(self, interaction, note=None):
        content, embed = self._render(note)
        await interaction.response.edit_message(content=content, embed=embed, view=self)

    async def reload_current(self, interaction, note=None):
        """Re-fetch pending rows after an edit and re-display, keeping position sane."""
        self.rows = problems.get_pending_submissions()
        if self.index >= len(self.rows):
            self.index = max(0, len(self.rows) - 1)
        await self._refresh(interaction, note)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.current_row()
        if row is None:
            await self._refresh(interaction)
            return
        problems.approve_submission(row[0])
        self.rows.pop(self.index)
        if self.index >= len(self.rows):
            self.index = max(0, len(self.rows) - 1)
        await self._refresh(interaction, note=f"✅ Approved #{row[0]}.")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.current_row()
        if row is None:
            await self._refresh(interaction)
            return
        problems.reject_submission(row[0])
        self.rows.pop(self.index)
        if self.index >= len(self.rows):
            self.index = max(0, len(self.rows) - 1)
        await self._refresh(interaction, note=f"❌ Rejected #{row[0]}.")

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.current_row()
        if row is None:
            await self._refresh(interaction)
            return
        await interaction.response.send_modal(EditProblemModal(row, on_saved=self.reload_current))

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.rows and self.index < len(self.rows) - 1:
            self.index += 1
        await self._refresh(interaction)


@bot.tree.command(name="reviewproblem", description="Review pending problem submissions")
@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.has_permissions(manage_messages=True)
async def reviewproblem(interaction: discord.Interaction):
    view = ReviewView(interaction.user.id)
    content, embed = view._render()
    if embed is None:
        await interaction.response.send_message(content, ephemeral=True)
        return
    await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=True)

def _full_problem_embed(row, index=None, total=None, moderator_view=False):
    (_id, category, prompt, answer, difficulty, latex, image_url,
     submitted_by, approved, created_at) = row
    label = CATEGORY_LABELS.get(category, category)
    status = "✅ Approved" if approved else "🕓 Pending"
    embed = discord.Embed(
        title=f"Problem #{_id} — {label}",
        color=BRAND_COLOR if approved else discord.Color.orange(),
    )
    embed.add_field(name="Problem", value=(prompt or "—")[:1024], inline=False)
    # Only moderators see the answer inline (this embed is only used in mod flows / by-id lookups).
    embed.add_field(name="Answer", value=(answer or "—")[:1024], inline=False)
    embed.add_field(name="Difficulty", value=str(difficulty or "—"), inline=True)
    embed.add_field(name="LaTeX", value="On" if latex else "Off", inline=True)
    if moderator_view:
        embed.add_field(name="Status", value=status, inline=True)
    if image_url:
        embed.set_image(url=image_url)
    footer_bits = []
    if index is not None and total is not None:
        footer_bits.append(f"{index + 1} of {total}")
    if submitted_by:
        footer_bits.append(f"Submitted by {submitted_by}")
    if footer_bits:
        embed.set_footer(text=" • ".join(footer_bits))
    return embed

class BrowseView(discord.ui.View):
    def __init__(self, moderator_id, rows):
        super().__init__(timeout=300)
        self.moderator_id = moderator_id
        self.rows = rows
        self.index = 0

    def current_row(self):
        if 0 <= self.index < len(self.rows):
            return self.rows[self.index]
        return None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.moderator_id:
            await interaction.response.send_message(
                "This browse session isn't yours — run `/editproblem` yourself.",
                ephemeral=True,
            )
            return False
        return True

    def _render(self, note=None):
        row = self.current_row()
        if row is None:
            for child in self.children:
                child.disabled = True
            content = (note + "\n" if note else "") + "🙈 No problems to show."
            return content.strip(), None
        return (note or None), _full_problem_embed(
            row, index=self.index, total=len(self.rows), moderator_view=True
        )

    async def _refresh(self, interaction, note=None):
        content, embed = self._render(note)
        await interaction.response.edit_message(content=content, embed=embed, view=self)

    async def reload_after_edit(self, interaction, note=None):
        # Re-fetch the edited row so the embed reflects saved changes.
        row = self.current_row()
        if row is not None:
            fresh = problems.get_problem(row[0])
            if fresh is not None:
                self.rows[self.index] = fresh
        await self._refresh(interaction, note)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
        await self._refresh(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < len(self.rows) - 1:
            self.index += 1
        await self._refresh(interaction)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.current_row()
        if row is None:
            await self._refresh(interaction)
            return
        await interaction.response.send_modal(EditProblemModal(row, on_saved=self.reload_after_edit))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.current_row()
        if row is None:
            await self._refresh(interaction)
            return
        deleted_id = row[0]
        problems.delete_problem(deleted_id)
        self.rows.pop(self.index)
        if self.index >= len(self.rows):
            self.index = max(0, len(self.rows) - 1)
        await self._refresh(interaction, note=f"🗑️ Deleted #{deleted_id}.")


@bot.tree.command(name="editproblem", description="Search by ID or browse the full problem database to edit problems")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(
    problem_id="Jump straight to a specific problem ID (optional).",
    category="Only browse this category (optional).",
    status="Only browse approved or pending problems (optional).",
)
@app_commands.choices(
    category=CATEGORY_CHOICES,
    status=[
        app_commands.Choice(name="Approved only", value="approved"),
        app_commands.Choice(name="Pending only", value="pending"),
    ],
)
@app_commands.checks.has_permissions(manage_messages=True)
async def editproblem(
    interaction: discord.Interaction,
    problem_id: int | None = None,
    category: app_commands.Choice[str] | None = None,
    status: app_commands.Choice[str] | None = None,
):
    
    if problem_id is not None:
        row = problems.get_problem(problem_id)
        if row is None:
            await interaction.response.send_message(
                f"No problem found with ID `{problem_id}`.", ephemeral=True
            )
            return
        view = BrowseView(interaction.user.id, [row])
        content, embed = view._render()
        await interaction.response.send_message(
            content=content, embed=embed, view=view, ephemeral=True
        )
        return

    approved = None
    if status is not None:
        approved = (status.value == "approved")
    rows = problems.get_all_problems(
        category=category.value if category else None,
        approved=approved,
    )
    if not rows:
        await interaction.response.send_message(
            "No problems match those filters.", ephemeral=True
        )
        return
    view = BrowseView(interaction.user.id, rows)
    content, embed = view._render()
    await interaction.response.send_message(
        content=content, embed=embed, view=view, ephemeral=True
    )


@bot.tree.command(name="deleteproblem", description="Permanently delete a problem by ID")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(problem_id="The ID of the problem to delete")
@app_commands.checks.has_permissions(manage_messages=True)
async def deleteproblem(interaction: discord.Interaction, problem_id: int):
    row = problems.get_problem(problem_id)
    if row is None:
        await interaction.response.send_message(
            f"No problem found with ID `{problem_id}`.", ephemeral=True
        )
        return
    problems.delete_problem(problem_id)
    label = CATEGORY_LABELS.get(row[1], row[1])
    await interaction.response.send_message(
        f"🗑️ Deleted problem #{problem_id} ({label}).", ephemeral=True
    )

async def _relay_to_feedback_channel(embed):
    """Sends an embed to the configured feedback channel. Returns True on success."""
    channel_id = os.getenv("FEEDBACK_CHANNEL")
    if not (channel_id and channel_id.isdigit()):
        return False
    channel = bot.get_channel(int(channel_id))
    if channel is None:
        return False
    try:
        await channel.send(embed=embed)
        return True
    except discord.DiscordException:
        return False


@bot.tree.command(name="reportproblem", description="Report a problem that's wrong or broken")
@app_commands.describe(
    problem_id="The ID of the problem you're reporting",
    reason="What's wrong with it",
)
async def reportproblem(interaction: discord.Interaction, problem_id: int, reason: str):
    row = problems.get_problem(problem_id)
    if row is None:
        await interaction.response.send_message(
            f"No problem found with ID `{problem_id}`.", ephemeral=True
        )
        return
    embed = discord.Embed(
        title=f"🚩 Problem #{problem_id} reported",
        description=reason,
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="Problem", value=(row[2] or "—")[:1024], inline=False)
    embed.set_author(
        name=str(interaction.user),
        icon_url=interaction.user.display_avatar.url,
    )
    embed.set_footer(text="Use /editproblem or /deleteproblem to resolve.")
    relayed = await _relay_to_feedback_channel(embed)
    if not relayed:
        print(f"[report] #{problem_id} reported by @{interaction.user}: {reason!r}")
    await interaction.response.send_message(
        "Thanks for the report! Someone on our staff team will review it shortly. 🙏", ephemeral=True
    )


@bot.tree.command(name="randpotw", description="View a random MathEXplained problem of the week")
async def randpotw(interaction: discord.Interaction):
    await interaction.response.send_message("🤫 This command is not ready yet!", ephemeral=True)
    # WEBMASTER_TODO: discuss


@bot.tree.command(name="randcrossword", description="View a random MathEXplained crossword puzzle")
async def randcrossword(interaction: discord.Interaction):
    await interaction.response.send_message("🤫 This command is not ready yet!", ephemeral=True)
    # WEBMASTER_TODO: discuss


@bot.tree.command(name="randspread", description="View a random MathEXplained math spread")
async def randspread(interaction: discord.Interaction):
    await interaction.response.send_message("🤫 This command is not ready yet!", ephemeral=True)
    # WEBMASTER_TODO: discuss

# --- duel game logic --- #

# Active duels keyed by channel id, so on_message can route answers to them.
active_duels: dict[int, "DuelGame"] = {}

# Bot difficulty → how long (seconds) the bot "thinks" before answering a round.
# Scaled slightly by the problem's own difficulty so harder problems buy more time.
BOT_MODE_BASE_TIME = {
    "easy": 40.0,      # slow bot — lots of room for the human
    "medium": 25.0,
    "hard": 15.0,
    "mathlete": 10.0,   # very fast — you'd better be quick
}
BOT_MODE_CHOICES = [
    app_commands.Choice(name="Easy", value="easy"),
    app_commands.Choice(name="Medium", value="medium"),
    app_commands.Choice(name="Hard", value="hard"),
    app_commands.Choice(name="Mathlete", value="mathlete"),
]

# How long players have to answer each round before it's called a draw.
ROUND_TIMEOUT_SECONDS = 45.0

def _normalize_answer(text: str) -> str:
    """Loose normalization so '1 / 2' matches '1/2', case-insensitively."""
    return "".join(text.split()).lower()

def bot_answer_delay(mode: str, difficulty: int | None) -> float:
    base = BOT_MODE_BASE_TIME.get(mode, BOT_MODE_BASE_TIME["medium"])
    # Each difficulty point above 1 adds a little to the bot's think time.
    bonus = ((difficulty or 5) - 1) * (base * 0.1)
    return base + bonus

class DuelGame:
    """A best-of-N duel run in one channel: human vs human, or human vs bot."""

    def __init__(self, channel, rounds, problems_list, players, bot_mode=None):
        self.channel = channel
        self.rounds = rounds
        self.problems = problems_list
        self.players = players            # list of discord.User/Member (len 1 for vs-bot)
        self.bot_mode = bot_mode          # None for PvP, else easy/medium/hard/mathlete
        self.vs_bot = bot_mode is not None

        # Scores keyed by a stable id: user ids, plus BOT_ID for the bot.
        self.BOT_ID = 0
        self.scores = {p.id: 0 for p in players}
        if self.vs_bot:
            self.scores[self.BOT_ID] = 0

        self._round_active = False
        self._round_winner = None
        self._answer = None
        self._answer_norm = None
        self._round_event = None
        self._bot_task = None

    def name_for(self, ident):
        if ident == self.BOT_ID:
            return f"🤖 {bot.user.display_name}"
        for p in self.players:
            if p.id == ident:
                return p.display_name
        return "Unknown"

    async def on_message(self, message: discord.Message):
        """Called for every human message in the channel while the duel is live."""
        if not self._round_active or self._round_winner is not None:
            return
        if message.author.id not in self.scores:
            return  # spectators can't score
        if _normalize_answer(message.content) == self._answer_norm:
            self._round_winner = message.author.id
            if self._bot_task is not None:
                self._bot_task.cancel()
            if self._round_event is not None:
                self._round_event.set()

    async def _bot_answers_after(self, delay):
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        if self._round_active and self._round_winner is None:
            self._round_winner = self.BOT_ID
            if self._round_event is not None:
                self._round_event.set()

    async def _present_problem(self, row, round_no):
        _id, category, prompt, answer, difficulty, latex, image_url = row
        label = CATEGORY_LABELS.get(category, category)
        diff_txt = f" • Difficulty {difficulty}/10" if difficulty else ""
        embed = discord.Embed(
            title=f"⚔️ Round {round_no} of {self.rounds} — {label}{diff_txt}",
            color=BRAND_COLOR,
        )
        embed.set_footer(text="Type your answer in chat! First correct answer wins the round.")

        files = []
        if latex:
            try:
                png = await math_render.render_latex(prompt)
                files.append(discord.File(io.BytesIO(png), filename="problem.png"))
                embed.set_image(url="attachment://problem.png")
            except math_render.RenderError:
                embed.description = prompt  # fall back to raw text
        else:
            embed.description = prompt
        if image_url:
            embed.add_field(name="Image", value=f"[Attached image]({image_url})", inline=False)
        await self.channel.send(embed=embed, files=files)

    async def run(self):
        try:
            await self._run_rounds()
        finally:
            active_duels.pop(self.channel.id, None)

    async def _run_rounds(self):
        needed = self.rounds // 2 + 1  # majority clinches early
        for round_no, row in enumerate(self.problems[:self.rounds], start=1):
            answer = row[3]
            self._answer = answer
            self._answer_norm = _normalize_answer(answer or "")
            self._round_winner = None
            self._round_event = asyncio.Event()
            self._round_active = True

            await self._present_problem(row, round_no)

            if self.vs_bot:
                delay = bot_answer_delay(self.bot_mode, row[4])
                self._bot_task = asyncio.create_task(self._bot_answers_after(delay))

            try:
                await asyncio.wait_for(self._round_event.wait(), timeout=ROUND_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                pass
            finally:
                self._round_active = False
                if self._bot_task is not None:
                    self._bot_task.cancel()
                    self._bot_task = None

            if self._round_winner is None:
                await self.channel.send(
                    f"⏱️ Time! Nobody got it. The answer was **{answer}**."
                )
            else:
                self.scores[self._round_winner] += 1
                await self.channel.send(
                    f"✅ **{self.name_for(self._round_winner)}** takes round {round_no}! "
                    f"The answer was **{answer}**.\n{self._scoreline()}"
                )

            top = max(self.scores.values())
            if top >= needed:
                break

            await asyncio.sleep(2)

        await self._announce_winner()

    def _scoreline(self):
        return " • ".join(
            f"{self.name_for(ident)}: **{score}**" for ident, score in self.scores.items()
        )

    def _record_stats(self, leaders):
        """Records win/loss/draw for each human player on the leaderboard."""
        is_draw = len(leaders) > 1
        for p in self.players:
            if is_draw:
                result = "draw"
            elif p.id in leaders:
                result = "win"
            else:
                result = "loss"
            duelstats.record_result(p.id, p.display_name, result)

    async def _announce_winner(self):
        top = max(self.scores.values())
        leaders = [ident for ident, s in self.scores.items() if s == top]
        if len(leaders) == 1:
            winner = leaders[0]
            embed = discord.Embed(
                title="🏆 Duel over!",
                description=f"**{self.name_for(winner)}** wins the duel!\n\n{self._scoreline()}",
                color=discord.Color.gold(),
            )
        else:
            embed = discord.Embed(
                title="🤝 Duel over — it's a draw!",
                description=self._scoreline(),
                color=BRAND_COLOR,
            )
        self._record_stats(leaders)
        await self.channel.send(embed=embed)


class DuelChallengeView(discord.ui.View):
    """Accept/decline handshake shown to the challenged opponent."""
    def __init__(self, challenger, opponent, start_callback):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.start_callback = start_callback
        self.responded = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                "This challenge isn't for you.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.responded = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=f"⚔️ {self.opponent.mention} accepted! The duel begins…", view=self
        )
        self.stop()
        await self.start_callback()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.responded = True
        for child in self.children:
            child.disabled = True
        active_duels.pop(interaction.channel.id, None)
        await interaction.response.edit_message(
            content=f"🚫 {self.opponent.mention} declined the duel.", view=self
        )
        self.stop()

    async def on_timeout(self):
        if not self.responded:
            active_duels.pop(self.opponent.id, None)


@bot.tree.command(name="duelgame", description="Duel it out in a live math challenge")
@app_commands.describe(
    opponent="Who to duel. Leave empty to duel the bot.",
    bot_difficulty="Bot speed (only used when dueling the bot).",
    rounds="Number of rounds (best-of). Default 5.",
    category="Restrict problems to one category. Default: mixed.",
    min_difficulty="Minimum problem difficulty 1-10.",
    max_difficulty="Maximum problem difficulty 1-10.",
)
@app_commands.choices(category=CATEGORY_CHOICES, bot_difficulty=BOT_MODE_CHOICES)
async def duelgame(
    interaction: discord.Interaction,
    opponent: discord.Member | None = None,
    bot_difficulty: app_commands.Choice[str] | None = None,
    rounds: app_commands.Range[int, 1, 15] = 5,
    category: app_commands.Choice[str] | None = None,
    min_difficulty: app_commands.Range[int, 1, 10] | None = None,
    max_difficulty: app_commands.Range[int, 1, 10] | None = None,
):
    # One duel per channel at a time.
    if interaction.channel_id in active_duels:
        await interaction.response.send_message(
            "There's already a duel running in this channel — wait for it to finish.",
            ephemeral=True,
        )
        return

    # Validate opponent.
    vs_bot = opponent is None
    if not vs_bot:
        if opponent.bot:
            await interaction.response.send_message(
                "To duel the bot, just leave the opponent empty.", ephemeral=True
            )
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't duel yourself!", ephemeral=True
            )
            return

    if min_difficulty and max_difficulty and min_difficulty > max_difficulty:
        await interaction.response.send_message(
            "`min_difficulty` can't be greater than `max_difficulty`.", ephemeral=True
        )
        return

    # Pull problems for the duel.
    problem_rows = problems.get_duel_problems(
        rounds,
        category=category.value if category else None,
        min_difficulty=min_difficulty,
        max_difficulty=max_difficulty,
    )
    if not problem_rows:
        await interaction.response.send_message(
            "No approved problems match those settings — try widening the filters.",
            ephemeral=True,
        )
        return

    actual_rounds = min(rounds, len(problem_rows))
    cat_txt = category.name if category else "Mixed"
    diff_txt = "any"
    if min_difficulty or max_difficulty:
        diff_txt = f"{min_difficulty or 1}-{max_difficulty or 10}"

    # Reserve the channel immediately so a second /duelgame can't slip in.
    placeholder = DuelGame(interaction.channel, actual_rounds, problem_rows, [])
    active_duels[interaction.channel_id] = placeholder

    async def start_duel(players, bot_mode):
        game = DuelGame(interaction.channel, actual_rounds, problem_rows, players, bot_mode)
        active_duels[interaction.channel_id] = game
        await game.run()

    if vs_bot:
        mode = bot_difficulty.value if bot_difficulty else "medium"
        embed = discord.Embed(
            title="⚔️ Duel vs the bot",
            description=(
                f"**{interaction.user.display_name}** vs 🤖 **{bot.user.display_name}**\n\n"
                f"Rounds: **{actual_rounds}** • Category: **{cat_txt}** • "
                f"Difficulty: **{diff_txt}** • Bot mode: **{mode.title()}**"
            ),
            color=BRAND_COLOR,
        )
        await interaction.response.send_message(embed=embed)
        await start_duel([interaction.user], mode)
    else:
        async def on_accept():
            await start_duel([interaction.user, opponent], None)

        view = DuelChallengeView(interaction.user, opponent, on_accept)
        await interaction.response.send_message(
            content=(
                f"{opponent.mention}, **{interaction.user.display_name}** challenges you to a duel!\n"
                f"Rounds: **{actual_rounds}** • Category: **{cat_txt}** • Difficulty: **{diff_txt}**\n"
                f"Accept within 60 seconds."
            ),
            view=view,
        )
        # If the challenge is declined or times out, free the channel.
        async def cleanup():
            await view.wait()
            if not view.responded:
                active_duels.pop(interaction.channel_id, None)
        asyncio.create_task(cleanup())

@bot.tree.command(name="feedback", description="Provide feedback about the bot")
@app_commands.describe(message="Your feedback")
async def feedback(interaction: discord.Interaction, message: str):
    embed = discord.Embed(
        title="📩 New feedback",
        description=message,
        color=BRAND_COLOR,
        timestamp=datetime.now(),
    )
    embed.set_author(
        name=str(interaction.user),
        icon_url=interaction.user.display_avatar.url,
    )
    if interaction.guild is not None:
        embed.set_footer(text=interaction.guild.name)

    relayed = await _relay_to_feedback_channel(embed)
    if not relayed:
        print(f"[feedback] not relayed; @{interaction.user}'s feedback: {message!r}")

    await interaction.response.send_message(
        "Received! Thank you for your feedback! 💙", ephemeral=True
    )

@bot.tree.command(name="website", description="Visit the MathEXplained website")
async def website(interaction: discord.Interaction):
    embed = discord.Embed(
        title="MathEXplained",
        description=f"Explore spreads, crosswords, and more on our website.\n\n🌐 [Visit our website](https://mathexplained.github.io)",
        color=BRAND_COLOR,
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="apply", description="Apply to be a MathEXplained staff member")
async def apply(interaction: discord.Interaction):
    apply_url = "https://docs.google.com/forms/d/e/1FAIpQLSde9eR4UJXXm39MRJz1KDsjcta8wj2Fu6yVJPZ4WfLS2UDPKQ/viewform"
    if not apply_url:
        await interaction.response.send_message(
            "We currently aren't accepting applications — check back soon!", ephemeral=True
        )
        return
    embed = discord.Embed(
        title="Join the MathEXplained team",
        url=apply_url,
        description=f"Interested in helping out? Apply to become a staff member!\n\n📝 [Open the application]({apply_url})",
        color=BRAND_COLOR,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="View MathEXplained problem database stats")
async def stats(interaction: discord.Interaction):
    s = problems.get_stats()
    embed = discord.Embed(title="📊 MathEXplained Stats", color=BRAND_COLOR)
    embed.add_field(name="Approved problems", value=str(s["total_approved"]), inline=True)
    embed.add_field(name="Pending review", value=str(s["total_pending"]), inline=True)
    if s["avg_difficulty"] is not None:
        embed.add_field(
            name="Avg difficulty", value=f"{s['avg_difficulty']:.1f}/10", inline=True
        )
    if s["by_category"]:
        lines = [
            f"**{CATEGORY_LABELS.get(code, code)}**: {s['by_category'].get(code, 0)}"
            for code in problems.CATEGORIES
        ]
        embed.add_field(name="By category", value="\n".join(lines), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard", description="See the top duel players")
async def leaderboard(interaction: discord.Interaction):
    rows = duelstats.get_leaderboard(limit=10)
    if not rows:
        await interaction.response.send_message(
            "No duels have been played yet — start one with `/duelgame`!", ephemeral=True
        )
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, wins, losses, draws) in enumerate(rows):
        rank = medals[i] if i < len(medals) else f"**{i + 1}.**"
        total = wins + losses + draws
        lines.append(f"{rank} **{name}** — {wins}W / {losses}L / {draws}D ({total} played)")
    embed = discord.Embed(
        title="🏆 Duel Leaderboard",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="duelstats", description="View your own duel record")
async def duel_stats(interaction: discord.Interaction):
    wins, losses, draws = duelstats.get_user_stats(interaction.user.id)
    total = wins + losses + draws
    if total == 0:
        await interaction.response.send_message(
            "You haven't played any duels yet — try `/duelgame`!", ephemeral=True
        )
        return
    win_rate = wins / total * 100
    embed = discord.Embed(
        title=f"⚔️ {interaction.user.display_name}'s Duel Record",
        color=BRAND_COLOR,
    )
    embed.add_field(name="Wins", value=str(wins), inline=True)
    embed.add_field(name="Losses", value=str(losses), inline=True)
    embed.add_field(name="Draws", value=str(draws), inline=True)
    embed.add_field(name="Win rate", value=f"{win_rate:.0f}%", inline=True)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="help", description="List everything this bot can do")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 MathEXplained Bot — Commands",
        color=BRAND_COLOR,
    )
    embed.add_field(
        name="🧮 Problems",
        value=(
            "`/randproblem` — random problem by category\n"
            "`/problem` — view a specific problem by ID\n"
            "`/submitproblem` — submit a problem for review\n"
            "`/reportproblem` — flag a wrong/broken problem\n"
            "`/stats` — problem database stats"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚔️ Duels",
        value=(
            "`/duelgame` — duel another user or the bot\n"
            "`/leaderboard` — top duel players\n"
            "`/duelstats` — your own duel record"
        ),
        inline=False,
    )
    embed.add_field(
        name="✏️ Rendering",
        value=(
            "`/renderlatex` — render LaTeX as an image\n"
            "`/renderasy` — render Asymptote as an image"
        ),
        inline=False,
    )
    embed.add_field(
        name="ℹ️ General",
        value=(
            "`/website` — visit our website\n"
            "`/apply` — apply to join staff\n"
            "`/feedback` — send us feedback\n"
            "`/ping` — check bot latency"
        ),
        inline=False,
    )
    # Only show moderator commands to those who can use them.
    perms = interaction.user.guild_permissions if interaction.guild else None
    if perms and perms.manage_messages:
        embed.add_field(
            name="🛠️ Moderator",
            value=(
                "`/reviewproblem` — approve/reject/edit pending submissions\n"
                "`/editproblem` — search by ID or browse & edit any problem\n"
                "`/deleteproblem` — delete a problem by ID\n"
                "`/offenses` — view a user's moderation history"
            ),
            inline=False,
        )
    embed.set_footer(text="MathEXplained")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "🚫 You don't have permission to use this command."
    else:
        msg = "⚠️ Something went wrong running that command."
        print(f"[app_command_error] {error!r}")
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    bot.run(token)