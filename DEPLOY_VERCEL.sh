#!/bin/bash
# Quick deploy script for Vercel
# Run this from the project root

cd frontend

echo "🔐 Logging into Vercel..."
vercel login

echo "🚀 Deploying to Vercel..."
vercel --prod

echo "✅ Deployment complete!"
echo "💡 If this is your first deploy, you'll be asked to:"
echo "   - Link to existing project, or create new"
echo "   - Set Root Directory to 'frontend'"
echo "   - Set environment variable NEXT_PUBLIC_API_URL=https://home-fit-production.up.railway.app"

