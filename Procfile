{
  "$schema": "https://schema.up.railway.app/railway.json",
  "build": {
    "builder": "nixpacks",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "python bot.py",
    "restartPolicyType": "onFailure",
    "restartPolicyMaxRetries": 10
  }
}
