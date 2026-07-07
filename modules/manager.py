"""
modules/manager.py – Group/topic management
Reconstructed from manager.so analysis
"""
import asyncio
from logger import LOGGER
from master.database import db_instance
from pyrogram.errors import ChatAdminRequired, ChatWriteForbidden

async def create_topic(bot, GROUP_ID, subjectname):
    """Create a forum topic for a subject."""
    try:
        # Check if topic already exists
        existing = await db_instance.get_topic(GROUP_ID, subjectname)
        if existing:
            return existing

        # Create new topic
        result = await bot.create_forum_topic(
            chat_id=GROUP_ID,
            title=subjectname
        )
        forum_id = result.id
        await db_instance.save_topic(GROUP_ID, forum_id, subjectname)
        return forum_id
    except ChatAdminRequired:
        LOGGER.error(f"Bot needs admin rights to create topics in {GROUP_ID}")
        return None
    except ChatWriteForbidden:
        LOGGER.error(f"Bot cannot write in {GROUP_ID}")
        return None
    except Exception as e:
        LOGGER.error(f"create_topic error: {e}")
        return None


async def set_chat(bot, GROUP_ID, editable1):
    """Verify bot permissions in a group."""
    try:
        chat = await bot.get_chat(int(GROUP_ID))
        me = await bot.get_me()
        bot_member = await bot.get_chat_member(int(GROUP_ID), me.id)
        if bot_member.privileges:
            return True
        else:
            await editable1.edit_text(
                "<b>❌ Bot must be admin with all permissions in the group!</b>"
            )
            return False
    except Exception as e:
        await editable1.edit_text(f"<b>❌ Error: {e}</b>")
        return False
