# Logic Hub (Python Background Worker)

The Logic Hub acts as the centralized brain of the Smart Crowd Management ecosystem. It continuously pulls data from `live_locations` (User App GPS) and your AI cameras to dynamically calculate exact density scores and trigger `alerts`.

## Local Testing
1. Copy `.env.example` to a new file named `.env`.
2. Fill tracking URLs inside `.env` with your Supabase credentials:
   - `SUPABASE_URL`: Get this from Project Settings -> API in Supabase.
   - `SUPABASE_SERVICE_ROLE_KEY`: Get this from Project Settings -> API as well (Do NOT use the Anon key, because this script needs admin DB access).
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the script:
   ```bash
   python logic_hub.py
   ```

## Deploying to Koyeb (24/7 Cloud Worker - Free)
1. Push this folder to a GitHub Repository.
2. Sign up on [Koyeb](https://app.koyeb.com/).
3. Click **Create Service**.
4. Choose **GitHub** and select your repository.
5. In the Build and Deployment settings:
   - Type: **Worker** (This ensures no web server is required and the app just runs in the background).
   - Run Command: `python logic_hub.py`
6. In **Environment Variables**:
   - Add `SUPABASE_URL` and your URL.
   - Add `SUPABASE_SERVICE_ROLE_KEY` and your secret key.
7. Click **Deploy**. Since it is a Worker, Koyeb will keep it running indefinitely 24/7!
