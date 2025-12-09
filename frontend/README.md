# HomeFit Frontend

Next.js frontend for the HomeFit Livability Score API.

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Create `.env.local` file (optional, defaults to production API):
```bash
NEXT_PUBLIC_API_URL=https://home-fit-production.up.railway.app
```

3. Run development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Build for Production

```bash
npm run build
npm start
```

## Deployment on Vercel

1. Push the `frontend/` folder to your GitHub repository
2. Import project in Vercel dashboard
3. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Next.js (auto-detected)
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://home-fit-production.up.railway.app`
5. Deploy!

## Project Structure

```
frontend/
├── app/              # Next.js app directory
│   ├── page.tsx      # Main page
│   ├── layout.tsx    # Root layout
│   └── globals.css   # Global styles
├── components/       # React components
│   ├── LocationSearch.tsx
│   ├── ScoreDisplay.tsx
│   ├── PillarCard.tsx
│   └── ...
├── lib/              # Utilities
│   └── api.ts        # API client
├── types/            # TypeScript types
│   └── api.ts       # API response types
└── package.json
```

## Features

- ✅ Location search with address/ZIP input
- ✅ Total livability score display
- ✅ 9 pillar score cards with expandable details
- ✅ Loading states and error handling
- ✅ Responsive design with Tailwind CSS
- ✅ TypeScript for type safety

## API Integration

The frontend connects to the HomeFit API at:
- Production: `https://home-fit-production.up.railway.app`
- Can be configured via `NEXT_PUBLIC_API_URL` environment variable
