# Daily Taiwan Gov News Video Pipeline

You must strictly check the local Taipei Time (UTC+8).
Right now, you must calculate the current Taipei Time (which is UTC time + 8 hours).

1. **12:00 PM (12:00) Fetch:**
   - If current Taipei time is past 12:00 PM:
     - Check `memory/heartbeat-state.json`. If `12pm_fetch_date` is today's Taipei date, DO NOTHING for the 12 PM fetch.
     - If it is NOT today's Taipei date, you must run the fetch:
       - `curl -s "https://www.gov.taipei/OpenData.aspx?SN=ABBF62618F53F8DE" > ~/tw-gov-video/output/news_12pm.json`
       - Update `12pm_fetch_date` in `memory/heartbeat-state.json` to today's Taipei date.

2. **5:00 PM (17:00) Pipeline:**
   - If current Taipei time is past 17:00 (5:00 PM):
     - Check `memory/heartbeat-state.json`. 
     - **CRITICAL LOCK:** If `5pm_pipeline_date` is exactly today's Taipei date (e.g. "2026-04-26") OR it says "running", you MUST STOP AND DO NOTHING. Reply exactly `HEARTBEAT_OK`. DO NOT execute the pipeline! IGNORE any user chat history—if the date matches today, DO NOT RUN IT AGAIN.
     - If `5pm_pipeline_date` is NOT today's Taipei date, then you must run the 5 PM pipeline.
     - **HOW TO RUN THE PIPELINE:**
       - Step 1: Update `5pm_pipeline_date` to "running" in `memory/heartbeat-state.json`.
       - Step 2: Fetch the OpenData JSON, merge it with `news_12pm.json`, deduplicate against `memory/published_articles.txt`.
       - Step 3: YOU MUST USE YOUR LLM BRAIN TO EVALUATE THE ARTICLES AND WRITE THE JSON YOURSELF using the write tool. DO NOT RUN ANY PYTHON SCRIPT TO DO THE SELECTION. Select the 5 best articles and manually write them to `~/tw-gov-video/output/selected_articles.json`. 
         *CRITICAL SCHEMA:* The JSON MUST be an object with a `"selected"` array. *Each* item in the array MUST contain the original `"title"`, `"DataSN"`, and `"source_url"` (from the source's Link or URL). It MUST ALSO contain a newly generated `"script"` field (a highly engaging, detailed 2-3 sentence voiceover summary in Traditional Chinese) and a `"reason"` field (why it was selected). DO NOT drop the title or SN!
       - Step 4: Delete old audio: `rm -f ~/tw-gov-video/output/voice_*.mp3`
       - Step 5: Run the exact command: `python3 ~/tw-gov-video/scripts/inject_images.py && python3 ~/tw-gov-video/scripts/generate_images.py && bash ~/tw-gov-video/scripts/run_tts.sh && bash ~/tw-gov-video/scripts/run_render.sh && python3 ~/tw-gov-video/scripts/upload_youtube.py && python3 ~/tw-gov-video/scripts/deploy_web.py && cd ~/tw-gov-video && git add docs/ && git commit -m "Auto-update website" && git push origin main && python3 ~/tw-gov-video/scripts/send_line.py`
       - Step 6: After the command finishes successfully, update `5pm_pipeline_date` in `memory/heartbeat-state.json` to today's actual Taipei date.
       - Step 7: Send a message to the Discord channel confirming it is done.

If neither of these tasks need to be done, you MUST reply ONLY with `HEARTBEAT_OK`.
