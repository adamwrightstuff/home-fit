# Deployment Guide for HomeFit Frontend

The frontend is ready to deploy! Here are the best options:

## Option 1: Vercel (Recommended - Easiest)

Vercel is the official hosting platform for Next.js and offers the simplest deployment.

### Steps:

1. **Push your code to GitHub** (if not already):
   ```bash
   git add .
   git commit -m "Add frontend with search options"
   git push origin main
   ```

2. **Deploy to Vercel**:
   - Go to [vercel.com](https://vercel.com)
   - Sign up/login with GitHub
   - Click "Add New Project"
   - Import your repository
   - Configure:
     - **Root Directory**: `frontend`
     - **Framework Preset**: Next.js (auto-detected)
     - **Build Command**: `npm run build` (auto-detected)
     - **Output Directory**: `.next` (auto-detected)
   - Add environment variable:
     - **Name**: `NEXT_PUBLIC_API_URL`
     - **Value**: `https://home-fit-production.up.railway.app`
   - Click "Deploy"

3. **Your site will be live** at `https://your-project.vercel.app`

### Benefits:
- ✅ Free tier with generous limits
- ✅ Automatic HTTPS
- ✅ Automatic deployments on git push
- ✅ Global CDN
- ✅ Zero configuration needed

---

## Option 2: Railway

If you're already using Railway for your API, you can deploy the frontend there too.

### Steps:

1. **Install Railway CLI**:
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. **Create a new Railway project**:
   ```bash
   cd frontend
   railway init
   ```

3. **Configure build settings**:
   - Set **Root Directory**: `frontend`
   - Set **Build Command**: `npm run build`
   - Set **Start Command**: `npm start`

4. **Add environment variable**:
   ```bash
   railway variables set NEXT_PUBLIC_API_URL=https://home-fit-production.up.railway.app
   ```

5. **Deploy**:
   ```bash
   railway up
   ```

---

## Option 3: Netlify

Another popular option for static sites and Next.js.

### Steps:

1. **Push to GitHub** (if not already)

2. **Deploy to Netlify**:
   - Go to [netlify.com](https://netlify.com)
   - Sign up/login with GitHub
   - Click "Add new site" → "Import an existing project"
   - Select your repository
   - Configure:
     - **Base directory**: `frontend`
     - **Build command**: `npm run build`
     - **Publish directory**: `frontend/.next`
   - Add environment variable:
     - **Key**: `NEXT_PUBLIC_API_URL`
     - **Value**: `https://home-fit-production.up.railway.app`
   - Click "Deploy site"

---

## Option 4: Self-Hosted (Docker)

If you want to run it yourself:

### Create Dockerfile:

```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
ENV PORT 3000

CMD ["node", "server.js"]
```

### Update next.config.js:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone', // Add this for Docker
}

module.exports = nextConfig
```

### Build and run:

```bash
docker build -t home-fit-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=https://home-fit-production.up.railway.app home-fit-frontend
```

---

## Environment Variables

Regardless of deployment method, you need:

- `NEXT_PUBLIC_API_URL`: Your API endpoint (defaults to production if not set)

---

## Testing the Deployment

After deployment, test:
1. ✅ Search for a location
2. ✅ Verify priorities dropdowns work
3. ✅ Check "Include chains" checkbox
4. ✅ Check "Enable schools" checkbox
5. ✅ Verify scores display correctly

---

## Quick Deploy Commands (Vercel CLI)

If you prefer command line:

```bash
npm i -g vercel
cd frontend
vercel
# Follow prompts, set NEXT_PUBLIC_API_URL when asked
```

---

## Troubleshooting

### Build fails:
- Check that all dependencies are in `package.json`
- Run `npm run build` locally first to catch errors

### API calls fail:
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check CORS settings on your API
- Ensure API is accessible from the deployment domain

### Styles not loading:
- Ensure Tailwind CSS is properly configured
- Check that `globals.css` is imported in `layout.tsx`

