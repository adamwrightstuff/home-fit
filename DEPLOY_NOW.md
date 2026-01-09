# Deploy to Vercel - Web Interface (Step-by-Step)dude 

Your code is already on GitHub at: `adamwrightstuff/home-fit`

## Step-by-Step Instructions:

### 1. Go to Vercel
Open your browser and visit: **https://vercel.com**

### 2. Sign In
- Click "Sign Up" or "Log In"
- Choose "Continue with GitHub"
- Authorize Vercel to access your GitHub account

### 3. Create New Project
- Click the **"Add New..."** button (top right)
- Select **"Project"**

### 4. Import Your Repository
- You'll see a list of your GitHub repositories
- Find and click on: **`home-fit`** (or `adamwrightstuff/home-fit`)
- Click **"Import"**

### 5. Configure Project Settings
**IMPORTANT:** You need to change the Root Directory!

- Look for **"Root Directory"** section
- Click **"Edit"** or the pencil icon
- Change it from `.` (root) to: **`frontend`**
- Click **"Continue"** or **"Save"**

Other settings should auto-detect:
- Framework: Next.js ✅
- Build Command: `npm run build` ✅
- Output Directory: `.next` ✅

### 6. Add Environment Variable
- Scroll down to **"Environment Variables"** section
- Click **"Add"** or **"+ Add"**
- Enter:
  - **Name:** `NEXT_PUBLIC_API_URL`
  - **Value:** `https://home-fit-production.up.railway.app`
- Make sure it's checked for **Production**, **Preview**, and **Development**
- Click **"Save"**

### 7. Deploy!
- Click the big **"Deploy"** button
- Wait 2-3 minutes while it builds

### 8. Your Site is Live!
Once deployment completes, you'll see:
- ✅ A success message
- 🌐 A live URL like: `https://home-fit-xyz.vercel.app`

Click the URL to open your deployed site!

---

## After First Deployment

✅ **Automatic Deployments:** Every time you push to GitHub, Vercel will automatically redeploy your site!

✅ **No More Setup Needed:** You're all set!

---

## Troubleshooting

**Build fails?**
- Make sure Root Directory is set to `frontend`
- Check that `NEXT_PUBLIC_API_URL` environment variable is set

**Can't find your repo?**
- Make sure you're signed in with the correct GitHub account (`adamwrightstuff`)
- Check that the repo is public or you've granted Vercel access

**Site loads but API calls fail?**
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check your API is running at that URL
