"""
modules/tasks.py – Batch upload processing
Reconstructed from tasks.so analysis
"""
import os
import asyncio
from logger import LOGGER
from config import Config
from master.database import db_instance
from master.helper import (
    download_video, sanitize_name, send_vid,
    get_youtube_video_id, thumbnail_gen
)
from master.logdb import check_and_send_from_db
from constant import msg
from modules.manager import create_topic


async def process_batch_upload(bot, course_id, all_data):
    """Process and upload all files in a batch."""
    try:
        # Get batch info
        batch = await db_instance.get_batch(course_id, course_id)
        if not batch:
            # try getting by user_id? we don't have user_id here
            LOGGER.error(f"Batch not found for course_id: {course_id}")
            return

        course_name = batch.get("select", "Unknown")
        save_dir = f"downloads/{course_id}"
        credit = batch.get("credit", "")
        file_credit = batch.get("filename", "")
        thumb = batch.get("thumb", "")
        chat_id = batch.get("group_id")
        group_id = chat_id

        # Ensure directories
        os.makedirs(save_dir, exist_ok=True)

        p_count = 0
        v_count = 0

        for item in all_data:
            url = item.get("url")
            if not url:
                continue

            subjectname = item.get("subjectName", "Unknown Subject")
            topicname = item.get("topicName", "Unknown Topic")
            name = item.get("name", "file")
            file_type = item.get("type", "video")

            # Check if already uploaded
            if await db_instance.is_file_uploaded(course_id, url):
                LOGGER.info(f"Skipping already uploaded file: {url}")
                continue

            # Get or create topic/forum
            forum_id = None
            if subjectname:
                forum_id = await create_topic(bot, group_id, subjectname)

            # Build captions
            if credit and file_credit:
                credit_text = f"{credit} | {file_credit}"
            else:
                credit_text = credit or ""

            # YouTube handling
            yt_video_id = await get_youtube_video_id(url)
            if yt_video_id:
                # Send as YouTube link instead of downloading
                yt_url = f"https://www.youtube.com/watch?v={yt_video_id}"
                caption = msg.YT_VIDEO_CAPTION
                # Use inline keyboard to watch/download
                from constant.buttom import yt_keyboard
                await bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    reply_markup=yt_keyboard(yt_url, yt_url),
                    message_thread_id=forum_id
                )
                await db_instance.mark_file_uploaded(course_id, url, chat_id)
                continue

            # Determine caption template
            if file_type == "pdf":
                caption = msg.PDF_CAPTION_V2.format(
                    sanitize_name(name),
                    course_name,
                    topicname,
                    item.get("timestamp", ""),
                    credit_text
                )
                p_count += 1
            else:
                caption = msg.VIDEO_CAPTION_V2.format(
                    sanitize_name(name),
                    course_name,
                    topicname,
                    item.get("timestamp", ""),
                    credit_text
                )
                v_count += 1

            # Try to send from database (cached)
            sent = await check_and_send_from_db(
                bot, url, chat_id, caption, caption, p_count, v_count, forum_id
            )
            if sent:
                await db_instance.mark_file_uploaded(course_id, url, chat_id)
                continue

            # Download and send
            if file_type == "pdf":
                # PDF: simple download and send as document
                try:
                    filename = await download_video(url, name, save_dir, credit_text)
                    if filename:
                        await bot.send_document(
                            chat_id=chat_id,
                            document=filename,
                            caption=caption,
                            message_thread_id=forum_id
                        )
                        os.remove(filename)
                        await db_instance.mark_file_uploaded(course_id, url, chat_id)
                except Exception as e:
                    LOGGER.error(f"PDF upload error: {e}")
                    await bot.send_message(
                        Config.ADMIN_ID,
                        msg.ERROR_UPLOADING.format(name, url, str(e))
                    )
            else:
                # Video: download and send with thumbnail
                try:
                    video_path = await download_video(url, name, save_dir, credit_text)
                    if video_path:
                        thumb_path = await thumbnail_gen(thumb, video_path)
                        await send_vid(
                            bot, url, caption, video_path, name,
                            chat_id, forum_id, thumb_path
                        )
                        # Cleanup
                        if os.path.exists(video_path):
                            os.remove(video_path)
                        if thumb_path and os.path.exists(thumb_path):
                            os.remove(thumb_path)
                        await db_instance.mark_file_uploaded(course_id, url, chat_id)
                except Exception as e:
                    LOGGER.error(f"Video upload error: {e}")
                    await bot.send_message(
                        Config.ADMIN_ID,
                        msg.ERROR_UPLOADING.format(name, url, str(e))
                    )

        # Mark batch as completed
        await db_instance.save_batch_status(course_id, course_id, "completed")

        # Send completion summary
        await bot.send_message(
            Config.ADMIN_ID,
            msg.LAST_BATCH_COMPLETED.format(
                course_id,
                course_name,
                batch.get("price", "N/A"),
                p_count,
                v_count,
                datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            )
        )

    except Exception as e:
        LOGGER.error(f"process_batch_upload error: {e}")
