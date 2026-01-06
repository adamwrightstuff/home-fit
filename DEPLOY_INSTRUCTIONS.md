# Deployment Instructions - No Browser Required

## Option 1: Get Vercel Token (CLI Deployment)

1. **Get your Vercel token:**
   - Go to: https://vercel.com/account/tokens
   - Click "Create Token"
   - Name it (e.g., "home-fit-deploy")
   - Copy the token

2. **Deploy via CLI:**
   ```bash
   cd frontend
   vercel --token YOUR_TOKEN_HERE --yes
   ```

3. **Set environment variable:**
   ```bash
   vercel env add NEXT_PUBLIC_API_URL production
   # When prompted, enter: https://home-fit-production.up.railway.app
   ```

---

## Option 2: Railway Deployment (You're already using Railway)

Since you already use Railway for your API, you can deploy the frontend there too:

1. **Login to Railway:**
   ```bash
   railway login
   ```
   (This will give you a link to open in browser - you'll need to do this once)

2. **Create new service:**
   ```bash
   cd frontend
   railway init
   # Select "Create a new project" or "Add to existing project"
   ```

3. **Set environment variable:**
   ```bash
   railway variables set NEXT_PUBLIC_API_URL=https://home-fit-production.up.railway.app
   ```

4. **Deploy:**
   ```bash
   railway up
   ```

---

## Option 3: Manual Browser Steps (One-time setup)

If you prefer to use the web interface, you only need to do this once:

1. Open your browser and go to: **https://vercel.com**
2. Sign in with GitHub
3. Click "Add New Project"
4. Import `adamwrightstuff/home-fit`
5. Set Root Directory to: `frontend`
6. Add env var: `NEXT_PUBLIC_API_URL` = `https://home-fit-production.up.railway.app`
7. Click Deploy

After this initial setup, all future deployments happen automatically when you push to GitHub!

---

## Which should you choose?

- **Option 1 (Vercel Token)**: Best if you want CLI-only deployment
- **Option 2 (Railway)**: Best if you want everything in one place
- **Option 3 (Web Interface)**: Easiest one-time setup, then automatic

