# Custom Domain Setup Guide

This guide will help you host your Home Fit application on your own domain.

## Architecture Overview

- **Frontend**: Next.js app (currently on Vercel)
- **Backend API**: FastAPI (currently on Railway at `https://home-fit-production.up.railway.app`)

You'll need to configure custom domains for both services.

---

## Step 1: Set Up Custom Domain for Frontend (Vercel)

### Option A: Using Vercel Dashboard

1. **Go to your Vercel project**
   - Visit https://vercel.com/dashboard
   - Select your `home-fit` project

2. **Add Custom Domain**
   - Go to **Settings** → **Domains**
   - Click **"Add Domain"**
   - Enter your domain (e.g., `homefit.com` or `www.homefit.com`)
   - Click **"Add"**

3. **Configure DNS Records**
   Vercel will show you the DNS records you need to add:
   - **For apex domain** (e.g., `homefit.com`):
     - Type: `A` record
     - Name: `@` or leave blank
     - Value: IP addresses provided by Vercel (usually 4 IPs)
   - **For www subdomain** (e.g., `www.homefit.com`):
     - Type: `CNAME` record
     - Name: `www`
     - Value: `cname.vercel-dns.com.`

4. **Add DNS Records at Your Domain Registrar**
   - Log into your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.)
   - Go to DNS management
   - Add the records Vercel provided
   - Wait for DNS propagation (can take a few minutes to 48 hours)

5. **Verify Domain**
   - Vercel will automatically verify once DNS propagates
   - You'll see a green checkmark when it's ready

### Option B: Using Vercel CLI

```bash
cd frontend
vercel domains add yourdomain.com
vercel domains add www.yourdomain.com
```

Then follow the DNS instructions provided.

---

## Step 2: Set Up Custom Domain for Backend API (Railway)

### Using Railway Dashboard

1. **Go to your Railway project**
   - Visit https://railway.app/dashboard
   - Select your backend service

2. **Add Custom Domain**
   - Go to **Settings** → **Networking**
   - Under **"Custom Domain"**, click **"Generate Domain"** or **"Add Domain"**
   - Enter your API subdomain (e.g., `api.homefit.com`)
   - Railway will provide you with a CNAME record

3. **Configure DNS Record**
   - At your domain registrar, add:
     - Type: `CNAME` record
     - Name: `api` (or your chosen subdomain)
     - Value: The CNAME target provided by Railway (e.g., `something.up.railway.app`)

4. **Wait for Verification**
   - Railway will verify the domain automatically
   - This usually takes a few minutes

### Using Railway CLI

```bash
railway domain add api.yourdomain.com
```

Then add the CNAME record at your DNS provider.

---

## Step 3: Update Frontend Environment Variable

Once your backend custom domain is set up, you need to update the frontend to use it.

### Option A: Using Vercel Dashboard

1. Go to your Vercel project → **Settings** → **Environment Variables**
2. Find `NEXT_PUBLIC_API_URL`
3. Click **Edit**
4. Change the value from `https://home-fit-production.up.railway.app` to your custom domain (e.g., `https://api.homefit.com`)
5. Make sure it's enabled for **Production**, **Preview**, and **Development**
6. Click **Save**

### Option B: Using Vercel CLI

```bash
cd frontend
vercel env rm NEXT_PUBLIC_API_URL production
vercel env add NEXT_PUBLIC_API_URL production
# When prompted, enter: https://api.yourdomain.com
```

### Option C: Update in Code (Not Recommended)

You could also update the fallback in `frontend/lib/api.ts`, but using environment variables is better.

---

## Step 4: Redeploy Frontend

After updating the environment variable, trigger a new deployment:

### Option A: Automatic (if connected to GitHub)
- Just push any commit to your main branch
- Vercel will automatically redeploy

### Option B: Manual Redeploy
- Go to Vercel dashboard → **Deployments**
- Click the **"..."** menu on the latest deployment
- Select **"Redeploy"**

### Option C: Using CLI
```bash
cd frontend
vercel --prod
```

---

## Step 5: Verify Everything Works

1. **Test Frontend**
   - Visit your custom domain (e.g., `https://homefit.com`)
   - The site should load

2. **Test API Connection**
   - Open browser DevTools (F12)
   - Go to **Network** tab
   - Try searching for a location
   - Check that API requests go to your custom API domain (e.g., `https://api.homefit.com`)

3. **Check CORS (if needed)**
   - If you see CORS errors, you may need to update CORS settings in `main.py`
   - Look for the `CORSMiddleware` configuration
   - Add your frontend domain to allowed origins

---

## DNS Record Examples

Here's what your DNS records might look like:

```
Type    Name    Value
----    ----    -----
A       @       76.76.21.21        (Vercel IP - example)
A       @       76.76.21.22        (Vercel IP - example)
CNAME   www     cname.vercel-dns.com.
CNAME   api     xxxxx.up.railway.app
```

---

## Common Issues & Solutions

### Issue: Domain not verifying
- **Solution**: Wait longer (DNS can take up to 48 hours), double-check DNS records are correct

### Issue: SSL certificate not issued
- **Solution**: Both Vercel and Railway automatically provision SSL certificates via Let's Encrypt. Wait a few minutes after DNS verification.

### Issue: CORS errors
- **Solution**: Update CORS origins in `main.py` to include your custom frontend domain

### Issue: API calls still going to Railway domain
- **Solution**: Make sure you updated `NEXT_PUBLIC_API_URL` and redeployed. Clear browser cache.

### Issue: Subdomain not working
- **Solution**: Make sure you added the correct CNAME record at your DNS provider

---

## Optional: Using a Single Domain with Path Routing

If you prefer to use a single domain (e.g., `homefit.com` for frontend and `homefit.com/api` for backend), you would need:

1. **Reverse Proxy Setup** (e.g., using Cloudflare Workers, Nginx, or Vercel Edge Functions)
2. **Update API paths** in your frontend code
3. **Configure routing rules**

This is more complex and generally not recommended unless you have specific requirements.

---

## Cost Considerations

- **Vercel**: Custom domains are free on all plans
- **Railway**: Custom domains are free
- **Domain Registrar**: You'll need to purchase/own the domain (typically $10-15/year)

---

## Security Considerations

1. **HTTPS**: Both Vercel and Railway automatically provide SSL certificates
2. **CORS**: Make sure to restrict CORS origins to your actual domain in production
3. **Environment Variables**: Never commit API keys or secrets to your repository

---

## Next Steps After Setup

1. ✅ Test all functionality on your custom domain
2. ✅ Update any documentation or links that reference the old domains
3. ✅ Set up monitoring/analytics if desired
4. ✅ Consider setting up redirects from old domains to new ones

---

## Quick Reference Commands

```bash
# Check DNS propagation
dig yourdomain.com
nslookup yourdomain.com

# Test SSL certificate
curl -I https://yourdomain.com
curl -I https://api.yourdomain.com

# Verify environment variable
vercel env ls
```
