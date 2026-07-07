"""
modules/retasks.py – Recover incomplete batches
Reconstructed from retasks.so analysis
"""
import asyncio
import pytz
from datetime import datetime
from logger import LOGGER
from config import Config
from master.database import db_instance
from constant import msg
from modules import appxdata
from modules.tasks import process_batch_upload

IST = pytz.timezone('Asia/Kolkata')


async def recover_incomplete_batches(bot):
    """Check for incomplete batches and restart upload."""
    try:
        incomplete_batches = await db_instance.get_incomplete_batches()
        if not incomplete_batches:
            LOGGER.info("No incomplete batches found")
            return

        LOGGER.info(f"Found {len(incomplete_batches)} incomplete batches")

        for batch_info in incomplete_batches:
            try:
                user_id = batch_info.get("user_id")
                course_id = batch_info.get("course_id")
                if not course_id:
                    continue

                # Get full batch details
                batch = await db_instance.get_batch(user_id, course_id)
                if not batch:
                    LOGGER.warning(f"Batch not found in database: {course_id}")
                    continue

                # Notify admin
                await bot.send_message(
                    Config.ADMIN_ID,
                    msg.RECOVERING_BATCH.format(batch.get("select", "Unknown"))
                )

                # Re‑fetch data
                all_data = await appxdata.collect_data(
                    course_id,
                    batch.get("api"),
                    batch.get("token")
                )

                if not all_data:
                    LOGGER.warning(f"No data to recover for batch {course_id}")
                    continue

                # Restart upload
                await process_batch_upload(bot, course_id, all_data)

                # Mark as completed
                await db_instance.save_batch_status(user_id, course_id, "completed")

                # Send completion message
                await bot.send_message(
                    Config.ADMIN_ID,
                    msg.LAST_BATCH_COMPLETED.format(
                        course_id,
                        batch.get("select", "Unknown"),
                        "N/A",
                        len([x for x in all_data if x.get("type") == "pdf"]),
                        len([x for x in all_data if x.get("type") == "video"]),
                        datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S")
                    )
                )

            except Exception as e:
                LOGGER.error(f"Error recovering batch {course_id}: {e}")
                continue

    except Exception as e:
        LOGGER.error(f"recover_incomplete_batches error: {e}")
