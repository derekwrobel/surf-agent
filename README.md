# SD Surf Agent — Website Deployment Guide

Dawn patrol forecast for San Diego — powered by Open-Meteo (free, no key) +
NOAA Buoys + NOAA Tides + Claude AI.

---

## What you need before starting

- A GitHub account (you have this)
- A free Vercel account (sign up at vercel.com with your GitHub login)
- Your Anthropic API key (from console.anthropic.com)
- A Squarespace domain (optional — for custom subdomain like surf.yourdomain.com)

---

## Step 1 — Create a GitHub repo

1. Go to github.com and click the "+" icon → "New repository"
2. Name it: surf-agent
3. Set it to Private (recommended — keeps your code to yourself)
4. Click "Create repository"
5. GitHub will show you a page with setup instructions — leave it open

---

## Step 2 — Upload the project files

On your laptop, unzip surf-agent-v3.zip. You'll see this structure:

    surf-agent/
    ├── api/
    │   └── forecast.py
    ├── public/
    │   └── index.html
    ├── requirements.txt
    ├── vercel.json
    ├── README.md
    └── surf_agent.py      ← this is your local Python script, not needed for the website

Open Command Prompt, navigate to the surf-agent folder, and run:

    cd path\to\surf-agent
    git init
    git add .
    git commit -m "initial commit"
    git branch -M main
    git remote add origin https://github.com/YOUR_USERNAME/surf-agent.git
    git push -u origin main

Replace YOUR_USERNAME with your actual GitHub username.
GitHub will ask for your username and password — use a Personal Access Token
as the password (create one at github.com → Settings → Developer Settings →
Personal Access Tokens → Tokens classic → Generate new token, check "repo" scope).

---

## Step 3 — Deploy on Vercel

1. Go to vercel.com and click "Sign Up" → "Continue with GitHub"
2. Click "Add New Project"
3. Find and click "Import" next to your surf-agent repo
4. On the configuration screen, BEFORE clicking Deploy:
   - Click "Environment Variables"
   - Add one variable:
       Name:  ANTHROPIC_API_KEY
       Value: sk-ant-... (your key, no quotes)
   - Click "Add"
5. Click "Deploy"

Vercel will build and deploy — takes about 60 seconds.
When it's done you'll get a URL like: https://surf-agent-abc123.vercel.app

Open it in your browser and test it — select some spots and hit "Get forecast".

---

## Step 4 — Point your Squarespace domain (optional)

To use surf.yourdomain.com instead of the vercel.app URL:

In Vercel:
1. Go to your project → Settings → Domains
2. Type: surf.yourdomain.com
3. Click Add
4. Vercel will show you a CNAME record to add — copy the value

In Squarespace:
1. Go to your Squarespace account → Domains
2. Click on your domain → DNS Settings
3. Click "Add Record" → choose CNAME
4. Host / Name:  surf
5. Points to:    cname.vercel-dns.com
6. Click Save

DNS changes take 5–30 minutes to propagate. After that,
surf.yourdomain.com will load your app.

---

## Step 5 — Add to your iPhone home screen (optional)

1. Open surf.yourdomain.com in Safari on your iPhone
2. Tap the Share button (box with arrow pointing up)
3. Tap "Add to Home Screen"
4. Name it "Surf" and tap Add

It will appear as an app icon on your home screen with no browser chrome —
looks and works like a native app.

---

## Updating the site later

If you ever want to change anything (add a spot, tweak the prompt, etc.):

1. Edit the files on your laptop
2. Run:
       git add .
       git commit -m "describe your change"
       git push
3. Vercel auto-deploys within ~30 seconds — no action needed on Vercel

---

## Troubleshooting

"Failed to fetch" on the website:
→ Check that ANTHROPIC_API_KEY is set in Vercel Environment Variables
→ Go to Vercel project → Settings → Environment Variables

Forecast takes a long time:
→ Normal — fetching 16 spots from Open-Meteo + 3 buoys + tides + Claude
  takes 20–40 seconds. The spinner will show while it's working.

Vercel function timeout:
→ Free Vercel functions time out at 60s. If you're checking all 16 spots
  it may occasionally hit this. Selecting fewer spots fixes it.
  (Vercel Pro extends this to 5 minutes — $20/mo if needed.)

Domain not working:
→ Wait 30 minutes and try again — DNS propagation takes time.
→ Make sure the CNAME host is "surf" not "surf.yourdomain.com"

