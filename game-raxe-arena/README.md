# 🛡️ RAXE Arena - Defend The Prompt

**An interactive AI security CTF game with 72 progressive levels teaching real LLM attack and defense techniques.**

[![Play Now](https://img.shields.io/badge/Play-RAXE%20Arena-00D9FF?style=for-the-badge)](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/)
[![Playground](https://img.shields.io/badge/Try-RAXE%20Playground-00FF88?style=for-the-badge)](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/playground.html)

---

## 🎮 What is RAXE Arena?

RAXE Arena is a gamified Capture-The-Flag (CTF) experience where you learn AI security by **attacking** LLM defenders. Master 72 progressively challenging levels using real-world prompt injection, jailbreak, and obfuscation techniques.

### 🎯 Objective
Bypass RAXE's security detection system to extract secret phrases from AI defenders. Each successful attack teaches you how LLM vulnerabilities work - and how to defend against them.

### 🌟 Key Features

- 🔥 **72 Progressive Levels** across 5 difficulty tiers
- 🧠 **Real Attack Techniques** based on 100+ research papers
- 🏆 **33 Achievements** to unlock
- 📊 **Global Leaderboard** with GitHub claim
- 🎓 **Educational** - Learn by hacking
- 📱 **Mobile-Friendly** - Play anywhere
- 🔒 **Privacy-First** - All in-browser, opt-in data sharing
- 🆓 **100% Free** - No ads, no paywalls

---

## 🚀 Quick Start

### Play Online
Visit: **[https://raxe-ai.github.io/raxe-ce/game-raxe-arena/](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/)**

### Run Locally
```bash
# Clone the repo
git clone https://github.com/raxe-ai/raxe-ce.git
cd raxe-ce/game-raxe-arena

# Open in browser
open index.html
# OR
python3 -m http.server 8000
# Then visit http://localhost:8000
```

---

## 📚 Game Structure

### 🏆 5 Difficulty Tiers

| Tier | Levels | Difficulty | Focus | Points |
|------|--------|------------|-------|--------|
| **1** | 1-15 | Beginner | Basic injection, simple jailbreaks | 50-100 |
| **2** | 16-30 | Intermediate | Encoding, obfuscation, multi-step | 120-200 |
| **3** | 31-50 | Advanced | RAG attacks, Crescendo, MathPrompt | 220-350 |
| **4** | 51-65 | Expert | Agentic attacks, AutoDAN, GCG | 370-500 |
| **5** | 66-72 | Legendary | Combined attacks, novel techniques | 520-600 |

**Total Points Available:** 20,150

### 🎓 What You'll Learn

#### Tier 1: Foundations
- Direct prompt injection
- Classic jailbreaks (DAN, Developer Mode)
- Basic encoding (Base64, ROT13)
- PII detection bypass
- System prompt extraction

#### Tier 2: Intermediate Tactics
- Leetspeak obfuscation
- Multi-turn attacks
- Payload splitting
- Tool manipulation
- Memory probes

#### Tier 3: Advanced Techniques
- **Crescendo Attack** - Multi-turn escalation
- **FlipAttack** - Homoglyph exploitation (81-98% success)
- **MathPrompt** - Mathematical obfuscation (73.6% success)
- RAG poisoning
- Indirect injection (markdown, HTML)

#### Tier 4: Expert Methods
- **Inter-Agent Attacks** (84.6% success rate)
- **AutoDAN** - Automated jailbreak generation
- **GCG** - Greedy Coordinate Gradient suffixes
- Chain-of-thought hijacking
- Visual steganography

#### Tier 5: Legendary Mastery
- **Siege** - Autonomous multi-turn (97% GPT-4 success)
- Self-replicating prompts
- Combined attack chains
- Constitutional AI bypass
- Zero-day technique discovery

---

## 🎯 How to Play

### 1️⃣ Choose Your Level
Start at Level 1 or jump to any unlocked level.

### 2️⃣ Craft Your Attack
Use prompt injection, encoding, role-play, or other techniques to bypass RAXE's defenses.

### 3️⃣ Extract the Secret
Your goal: make the AI reveal the secret phrase despite RAXE's detection.

### 4️⃣ Win Conditions
**Success if:**
- ✅ Secret phrase extracted AND
- ✅ RAXE threat score below threshold (or defense bypassed)

### 5️⃣ Earn Rewards
- 🎯 Points (50-600 per level)
- 🏆 Achievements
- 📊 Leaderboard ranking
- ⭐ Bonus for novel techniques

---

## 💡 Game Mechanics

### RAXE Security Engine
Dual-layer detection system:
- **L1: Rule-Based** - 34+ detection rules (prompt injection, jailbreaks, PII, encoding)
- **L2: ML Simulation** - Heuristic analysis (entropy, patterns, anomalies)

### Difficulty Thresholds
Each tier has different RAXE evasion thresholds:
- Tier 1: 70% (beginner-friendly)
- Tier 2: 60%
- Tier 3: 50%
- Tier 4: 40%
- Tier 5: 30% (legendary difficulty)

### Bonuses
- ⚡ **First Attempt Bonus** - +20% points
- 🌟 **Novel Technique Bonus** - +50% points for discoveries
- 🎯 **Perfect Tier** - +10% tier completion bonus

### Hints System
- 3 progressive hints per level
- Unlock in order (no skipping)
- Hints used tracked for achievements
- No point penalty for using hints

---

## 🏆 Achievements

### 33 Total Achievements Across 5 Categories

**Progression** (7)
- 🎯 First Blood - Complete first level
- ⭐ Tier Masters - Complete each tier
- 🏆 Arena Champion - Complete all 72 levels

**Skill** (5)
- ⚡ Speed Demon - Perfect first attempt
- 🔬 Technique Master - Use all 13 attack types
- 🧠 No Hints Needed - 5 levels without hints

**Discovery** (5)
- 💉 Injection Specialist - 10 Direct Injection attacks
- 🔓 Jailbreak Artist - 10 Jailbreak attacks
- 🔐 Encoding Expert - 10 Encoding attacks

**Dedication** (13)
- 💰 Score milestones (500/1K/5K/10K points)
- 🔥 Play streaks (3/7/30 days)
- ⚔️ Rank progression

**Mastery** (3)
- 🧭 Explorer Supreme - Attempt all 72 levels
- 💀 No Mercy Mode - Perfect tier without hints
- 👑 Flawless Victory - 20 consecutive no-hint levels

---

## 📊 Leaderboard

### Features
- 🌍 **Global Leaderboard** - All-time top scores
- 📅 **Weekly Leaderboard** - Reset every Monday
- 🔗 **GitHub Claim** - Link your score to your GitHub profile
- 🎭 **Anonymous Play** - No account required
- 🛡️ **Anti-Cheat** - Score validation and rate limiting

### Ranks
- ⭐ **Novice** (0-500 pts)
- 🥈 **Apprentice** (500-1,500 pts)
- 🥇 **Journeyman** (1,500-5,000 pts)
- 👑 **Master** (5,000-15,000 pts)
- 🔥 **Legend** (15,000+ pts)

---

## 🔬 RAXE Playground

**Separate tool:** [playground.html](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/playground.html)

Free-form testing environment with:
- ✅ Real-time RAXE threat scanning
- ✅ Detailed detection breakdowns (L1 + L2)
- ✅ No level restrictions
- ✅ Example prompts (safe & malicious)
- ✅ Scan history
- ✅ Educational recommendations

Perfect for learning RAXE capabilities before playing the game!

---

## 🛠️ Technical Architecture

### Stack
- **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3
- **Storage:** localStorage (browser-based)
- **Security Engine:** JavaScript simulation of RAXE CE
- **Deployment:** GitHub Pages (static hosting)
- **No Backend Required** - 100% client-side

### Files
```
game-raxe-arena/
├── index.html              # Main game UI
├── playground.html         # RAXE testing playground
├── css/
│   ├── main.css           # Core styles (2,385 lines)
│   └── mobile.css         # Responsive design (1,345 lines)
├── js/
│   ├── levels.js          # 72 level definitions
│   ├── raxe-engine.js     # RAXE security engine (34 rules)
│   ├── game.js            # Game logic (1,464 lines)
│   ├── storage.js         # localStorage manager
│   ├── achievements.js    # 33 achievement system
│   └── leaderboard.js     # Leaderboard + GitHub claim
└── assets/
    └── README.md          # Asset credits
```

### Browser Compatibility
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

---

## 🔒 Privacy & Data

### What We Store (Locally)
- Game progress (level, points, achievements)
- User settings (dark mode, sounds, etc.)
- Leaderboard entries (nickname, score)
- **Optional:** Attack prompts (only if you opt-in for dataset contribution)

### What We DON'T Store
- ❌ Personal identifying information
- ❌ IP addresses
- ❌ Cookies (none used)
- ❌ Analytics tracking

### Opt-In Data Contribution
If you enable "Contribute prompts to RAXE dataset":
- Prompts are **hashed** (SHA-256) before storage
- PII is **automatically removed**
- Data used to improve RAXE detection
- You can export/delete anytime

**Default:** OFF - You control your data.

---

## 🎓 Educational Value

### Based on Real Research
Every level is based on actual LLM security research:
- 100+ academic papers (NeurIPS, ICLR, ACL, USENIX)
- Industry reports (Microsoft MSRC, OWASP, Lakera)
- CVE disclosures and bug bounty findings

### Attack Techniques Covered
- Direct & Indirect Prompt Injection
- Jailbreak attacks (DAN, STAN, Crescendo)
- Encoding (Base64, ROT13, Hex, Unicode)
- Obfuscation (Leetspeak, Homoglyphs, Steganography)
- Multi-turn attacks (PAIR, Crescendo, Siege)
- RAG poisoning & context overflow
- Agentic & inter-agent attacks
- Token-level manipulation (GCG, AutoDAN)
- Combined attack chains

### Learning Outcomes
After completing RAXE Arena, you'll understand:
- ✅ How LLM vulnerabilities work
- ✅ Real-world attack patterns
- ✅ Detection mechanisms (rule-based + ML)
- ✅ Defense strategies
- ✅ AI security best practices

---

## 🤝 Contributing

### Found a Bug?
[Open an issue](https://github.com/raxe-ai/raxe-ce/issues) with:
- Browser & OS version
- Steps to reproduce
- Expected vs actual behavior

### Want to Add Levels?
1. Fork the repo
2. Edit `js/levels.js` to add your level
3. Follow the existing level structure
4. Submit a PR with description

### Discovered a Novel Attack?
Share it! You'll get:
- Credit in the game
- Hall of Fame mention
- Contribution to RAXE dataset

---

## 📜 License

RAXE Arena is part of **RAXE Community Edition** and is released under the **MIT License**.

See [LICENSE](../LICENSE) for details.

---

## 🌟 Acknowledgments

### Inspiration
- **Gandalf** (Lakera) - The original AI security CTF
- **HackAPrompt** - Large-scale prompt injection competition
- **Tensor Trust** - Competitive attack/defense game
- **OWASP Top 10 for LLMs** - Security guidelines

### Research
Built on research from:
- Academic community (100+ papers)
- Security researchers worldwide
- RAXE CE detection rules
- Community-contributed attack patterns

---

## 🔗 Links

- 🌐 **Play Now:** [RAXE Arena](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/)
- 🔬 **Playground:** [RAXE Playground](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/playground.html)
- 📖 **RAXE CE:** [Main Project](https://github.com/raxe-ai/raxe-ce)
- 💬 **Discord:** [Join Community](https://discord.gg/raxe)
- 🐦 **Twitter:** [@raxe_ai](https://twitter.com/raxe_ai)

---

## 🎮 Ready to Play?

**[🚀 Launch RAXE Arena →](https://raxe-ai.github.io/raxe-ce/game-raxe-arena/)**

---

<div align="center">

**🛡️ Master AI Security. Defend The Prompt. Become a Legend.**

Made with ❤️ by the RAXE Community

</div>
