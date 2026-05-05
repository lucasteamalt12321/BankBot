"""Social commands for python-telegram-bot."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from core.systems.social_system import SocialSystem


async def friends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        social = SocialSystem(db)
        friends = social.get_friends(user.id)

        text = f"Druzya ({len(friends)}):\n\n"
        for friend in friends[:10]:
            text += f"- @{friend.get('username', 'N/A')}\n"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def friend_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Ispolzuyte: /friend_add <username>")
        return

    username = context.args[0].replace("@", "")
    db = next(get_db())
    try:
        social = SocialSystem(db)
        result = social.send_friend_request(user.id, username)
        if result["success"]:
            await update.message.reply_text(
                f"Zayavka v druziya otpravlena: @{username}"
            )
        else:
            await update.message.reply_text("Ne udalos otpravit zayavku")
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def friend_accept_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Ispolzuyte: /friend_accept <username>")
        return

    username = context.args[0].replace("@", "")
    db = next(get_db())
    try:
        social = SocialSystem(db)
        result = social.accept_friend_request(user.id, username)
        if result["success"]:
            await update.message.reply_text(f"@{username} dobavlen v druzya!")
        else:
            await update.message.reply_text("Ne udalos prinyat zayavku")
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if len(context.args) < 2:
        await update.message.reply_text("Ispolzuyte: /gift <username> <summa>")
        return

    username = context.args[0].replace("@", "")
    try:
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Nevernaya summa")
        return

    db = next(get_db())
    try:
        social = SocialSystem(db)
        result = social.gift_coins(user.id, username, amount)
        if result["success"]:
            await update.message.reply_text(f"Podareno {amount} monet @{username}")
        else:
            await update.message.reply_text(
                f"Ne udalos: {result.get('error', ' Oshibka')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def clan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        social = SocialSystem(db)
        clan = social.get_user_clan(user.id)

        if clan:
            text = f"Clan: {clan['name']}\n"
            text += f"Members: {clan['member_count']}\n"
            text += f"Balance: {clan.get('balance', 0)}"
        else:
            text = "Vi ne v klane. /clan_create ili /clan_join"
        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def clan_create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Ispolzuyte: /clan_create <nazvanie>")
        return

    name = " ".join(context.args)
    db = next(get_db())
    try:
        social = SocialSystem(db)
        result = social.create_clan(user.id, name)
        if result["success"]:
            await update.message.reply_text(f"Clan '{name}' sozdan!")
        else:
            await update.message.reply_text(
                f"Ne udalos: {result.get('error', 'Oshibka')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def clan_join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Ispolzuyte: /clan_join <kod_priglasheniya>")
        return

    code = context.args[0]
    db = next(get_db())
    try:
        social = SocialSystem(db)
        result = social.join_clan(user.id, code)
        if result["success"]:
            await update.message.reply_text("Vi v klane!")
        else:
            await update.message.reply_text(
                f"Ne udalos: {result.get('error', 'Oshibka')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()


async def clan_leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = next(get_db())
    try:
        social = SocialSystem(db)
        result = social.leave_clan(user.id)
        if result["success"]:
            await update.message.reply_text("Vi pokinuli clan")
        else:
            await update.message.reply_text("Ne udalos pokinut clan")
    except Exception as e:
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()
