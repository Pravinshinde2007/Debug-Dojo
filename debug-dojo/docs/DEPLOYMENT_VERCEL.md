# Deploying Debug Dojo to Vercel 🚀

Yes, you can deploy both the **React + Vite Frontend** and the **FastAPI Backend** together on Vercel as a single project!

---

## 🏗️ How it Works on Vercel
1. **Frontend:** Vercel builds the React + Vite static bundle into `dist` and serves it on global Edge CDN.
2. **Backend:** Vercel detects `api/index.py` and uses the `@vercel/python` Serverless Runtime to serve FastAPI routes under `/api/*`.
3. **Database & Logs:** On Vercel's read-only serverless filesystem, the SQLite database and logs automatically use `/tmp` (`/tmp/debug_dojo.db` and `/tmp/logs/llm.jsonl`).

---

## ⚡ Deployment Methods

### Option 1: Via Vercel CLI (Fastest)

1. **Install Vercel CLI** (if you don't have it):
   ```bash
   npm install -g vercel
   ```

2. **Deploy directly from the terminal**:
   ```bash
   # From the project root:
   vercel
   ```
   Follow the CLI prompts:
   - *Set up and deploy?* **`y`**
   - *Which scope?* (Select your Vercel account)
   - *Link to existing project?* **`N`**
   - *What's your project's name?* **`debug-dojo`**
   - *In which directory is your code located?* **`./`** (or `./debug-dojo` if deploying from subfolder)
   - *Want to modify these settings?* **`N`** (Vercel will automatically read `vercel.json`)

3. **Deploy to Production**:
   ```bash
   vercel --prod
   ```

---

### Option 2: Via GitHub & Vercel Dashboard

1. **Push your code to a GitHub repository**:
   ```bash
   git add .
   git commit -m "feat: setup Debug Dojo with Vercel deployment"
   git push origin main
   ```

2. Go to **[vercel.com/new](https://vercel.com/new)** and import your repository.
3. If your code is inside the `debug-dojo` folder, set **Root Directory** to `debug-dojo`.
4. Click **Deploy**. Vercel will build the frontend and deploy the serverless Python functions automatically.

---

## ⚠️ Important Hackathon & Production Considerations

### 1. SQLite Persistence on Serverless
- **Behavior:** Vercel serverless functions are ephemeral. The database located at `/tmp/debug_dojo.db` will persist across warm function invocations, but will reset upon cold starts or across different global lambda instances.
- **For Hackathon Demos:** This is perfectly fine for live demo evaluation.
- **For Permanent Production Persistence:** You can point `DEBUG_DOJO_DB` to a hosted serverless database (such as **Turso** for SQLite via libSQL, or **Supabase / Neon** for PostgreSQL).

### 2. Child Process Execution Sandboxing (Rule 1)
- Vercel functions run inside AWS Lambda MicroVMs.
- While child processes (`subprocess.Popen`) can be spawned, custom low-level Linux kernel cgroups and network namespace isolation are constrained by Lambda.
- For maximum security when running arbitrary learner code with full memory/cgroup sandboxing, platforms like **Docker / Render / Railway / Fly.io** or a dedicated VPS are recommended for the runner component.
