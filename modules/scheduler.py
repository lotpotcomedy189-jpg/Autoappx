"""
modules/scheduler.py – Daily update scheduler
Reconstructed from scheduler.so analysis
"""
import asyncio
import pytz
from datetime import datetime, timedelta
from logger import LOGGER
from config import Config
from master.database import db_instance
from constant import msg
from modules import appxdata
from modules.tasks import process_batch_upload

IST = pytz.timezone('Asia/Kolkata')


async def get_next_run_time(time_str):
    """Calculate next run time based on HH:MM in IST."""
    try:
        now = datetime.now(IST)
        hour, minute = map(int, time_str.split(":"))
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run
    except Exception as e:
        LOGGER.error(f"get_next_run_time error: {e}")
        return None


async def schedule_batch_update(bot, course_id, api_url, time_str, token, length, course_name, group_id, price):
    """Schedule a batch update and run it at the given time."""
    try:
        next_run = await get_next_run_time(time_str)
        if not next_run:
            return

        now = datetime.now(IST)
        sleep_seconds = (next_run - now).total_seconds()
        LOGGER.info(f"Scheduled update for {course_name} at {time_str} IST (sleep {sleep_seconds}s)")

        await asyncio.sleep(sleep_seconds)

        # Fetch new data
        all_data = await appxdata.collect_data(course_id, api_url, token)
        if not all_data:
            await bot.send_message(
                Config.ADMIN_ID,
                msg.NO_NEW_CLASSES.format(course_name)
            )
            return

        pdf_count = sum(1 for x in all_data if x.get("type") == "pdf")
        video_count = sum(1 for x in all_data if x.get("type") == "video")

        # Process upload
        await process_batch_upload(bot, course_id, all_data)

        # Mark as completed
        await db_instance.save_batch_status(course_id, course_id, "completed")

        # Send completion notice
        await bot.send_message(
            Config.ADMIN_ID,
            msg.DAILY_UPDATE_COMPLETED.format(
                course_id,
                course_name,
                price or "N/A",
                pdf_count,
                video_count,
                datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")
            )
        )

    except Exception as e:
        LOGGER.error(f"schedule_batch_update error: {e}")


async def start_daily_schedulers(bot):
    """Start all schedulers from database."""
    try:
        batches = await db_instance.get_all_batches_with_schedule()
        if not batches:
            LOGGER.info("No batches with schedule found")
            return

        LOGGER.info(f"Starting {len(batches)} schedulers")

        for batch in batches:
            course_id = batch.get("course_id")
            api_url = batch.get("api")
            time_str = batch.get("time")
            token = batch.get("token")
            course_name = batch.get("select", "Unknown")
            group_id = batch.get("group_id")
            price = batch.get("price", 0)

            asyncio.create_task(
                schedule_batch_update(
                    bot, course_id, api_url, time_str, token,
                    batch.get("length", 0), course_name, group_id, price
                )
            )
            LOGGER.info(f"Started scheduler for {course_name} at {time_str}")

    except Exception as e:
        LOGGER.error(f"start_daily_schedulers error: {e}")
