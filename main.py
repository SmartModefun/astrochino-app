import os, jwt, httpx, json, hashlib, sqlite3, aiosqlite, random
from datetime import datetime, timedelta, timezone, date
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()
TZ_ARG = ZoneInfo("America/Argentina/Buenos_Aires")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.getenv("DB_PATH", "astrochino.db")
JWT_SECRET = os.getenv("JWT_SECRET") or "dev-secret-change-in-production"
LLM_API_KEY = os.getenv("LLM_API_KEY") or ""
GEMINI_MODEL = "gemini-2.5-flash"

# ── PayPal ───────────────────────────────────────────────
PAYPAL_SANDBOX = os.getenv("PAYPAL_SANDBOX", "false").lower() == "true"
if PAYPAL_SANDBOX:
    PAYPAL_CLIENT_ID = "ASEWf7lFIosrAjy8XwONVYkhL9FoKx1D64JsCvLl1qkfroMaR-r83_WhIMqTMnKycaKNv-2MyvokGQLF"
    PAYPAL_CLIENT_SECRET = "EMdfD7jFxprkW1VW9PWRkYOm8gVuimVq6zB2LH_pmxquYebSruGdfSY6EUPri9dG5VWc9ceeAXGS3Jp-"
    PAYPAL_WEBHOOK_ID = "8CP48652G95121503"
else:
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID") or ""
    PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET") or ""
    PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID") or ""
PAYPAL_BASE = "https://api-m.sandbox.paypal.com" if PAYPAL_SANDBOX else "https://api-m.paypal.com"
PREMIUM_PLAN_ID = os.getenv("PREMIUM_PLAN_ID") or ""
_paypal_cached_token = None
_paypal_cached_token_expires = 0

# ── Chinese Zodiac Data ──────────────────────────────
ANIMALS = [
    {"id": 0, "name": "Rata",   "name_en": "Rat",     "branch": "子", "hours": "23:00-01:00", "polarity": "Yang", "element": "Agua",   "trine": 0, "seasons": "Invierno medio"},
    {"id": 1, "name": "Buey",   "name_en": "Ox",      "branch": "丑", "hours": "01:00-03:00", "polarity": "Yin",  "element": "Tierra", "trine": 1, "seasons": "Invierno tardío"},
    {"id": 2, "name": "Tigre",  "name_en": "Tiger",   "branch": "寅", "hours": "03:00-05:00", "polarity": "Yang", "element": "Madera", "trine": 2, "seasons": "Primavera temprana"},
    {"id": 3, "name": "Conejo", "name_en": "Rabbit",  "branch": "卯", "hours": "05:00-07:00", "polarity": "Yin",  "element": "Madera", "trine": 3, "seasons": "Primavera media"},
    {"id": 4, "name": "Dragón", "name_en": "Dragon",  "branch": "辰", "hours": "07:00-09:00", "polarity": "Yang", "element": "Tierra", "trine": 0, "seasons": "Primavera tardía"},
    {"id": 5, "name": "Serpiente", "name_en": "Snake",  "branch": "巳", "hours": "09:00-11:00", "polarity": "Yin",  "element": "Fuego",  "trine": 1, "seasons": "Verano temprano"},
    {"id": 6, "name": "Caballo","name_en": "Horse",   "branch": "午", "hours": "11:00-13:00", "polarity": "Yang", "element": "Fuego",  "trine": 2, "seasons": "Verano medio"},
    {"id": 7, "name": "Cabra",  "name_en": "Goat",    "branch": "未", "hours": "13:00-15:00", "polarity": "Yin",  "element": "Tierra", "trine": 3, "seasons": "Verano tardío"},
    {"id": 8, "name": "Mono",   "name_en": "Monkey",  "branch": "申", "hours": "15:00-17:00", "polarity": "Yang", "element": "Metal",  "trine": 0, "seasons": "Otoño temprano"},
    {"id": 9, "name": "Gallo",  "name_en": "Rooster", "branch": "酉", "hours": "17:00-19:00", "polarity": "Yin",  "element": "Metal",  "trine": 1, "seasons": "Otoño medio"},
    {"id": 10, "name": "Perro", "name_en": "Dog",     "branch": "戌", "hours": "19:00-21:00", "polarity": "Yang", "element": "Tierra", "trine": 2, "seasons": "Otoño tardío"},
    {"id": 11, "name": "Cerdo", "name_en": "Pig",     "branch": "亥", "hours": "21:00-23:00", "polarity": "Yin",  "element": "Agua",   "trine": 3, "seasons": "Invierno temprano"},
]

ELEMENT_CYCLE = ["Madera", "Madera", "Fuego", "Fuego", "Tierra", "Tierra", "Metal", "Metal", "Agua", "Agua"]
ELEMENT_CYCLE_EN = ["Wood", "Wood", "Fire", "Fire", "Earth", "Earth", "Metal", "Metal", "Water", "Water"]

PERSONALIDAD = {
    "Rata": "Inteligente, carismática, adaptable y estratega. La Rata observa oportunidades donde otros no ven nada. Es astuta con el dinero y los negocios.",
    "Buey": "Leal, paciente, trabajador y confiable. El Buey construye a través de la perseverancia. Prefiere la estabilidad sobre la apariencia.",
    "Tigre": "Valiente, protector, inquieto y apasionado. El Tigre desafía lo injusto y empuja límites. Tiene un espíritu indomable.",
    "Conejo": "Elegante, diplomático, perceptivo y refinado. El Conejo busca armonía y sobrevive a través del tacto y la inteligencia social.",
    "Dragón": "Visionario, carismático, dramático y magnético. El Dragón atrae atención y tiene la fuerza del trueno primaveral.",
    "Serpiente": "Observadora, privada, inteligente e intensa. La Serpiente estudia patrones y nunca revela todos sus pensamientos.",
    "Caballo": "Activo, independiente, expresivo y amante de la libertad. El Caballo necesita velocidad, movimiento y experiencias directas.",
    "Cabra": "Gentil, creativa, relacional y sensible. La Cabra valora la pertenencia, la belleza y la conexión emocional.",
    "Mono": "Inventivo, ingenioso, técnico y resolutivo. El Mono juega con sistemas hasta encontrar una apertura.",
    "Gallo": "Preciso, observador, organizado y honesto. El Gallo nota lo que está fuera de orden y no teme decirlo.",
    "Perro": "Leal, justo, protector e íntegro. El Perro defiende la verdad y cuida de los suyos con devoción incondicional.",
    "Cerdo": "Generoso, sincero, indulgente y optimista. El Cerdo disfruta la vida y confía en la bondad del mundo."
}

LUCKY = {
    "Rata": {"numeros": [2, 3], "colores": ["Azul", "Dorado", "Verde"], "direccion": "Norte"},
    "Buey": {"numeros": [1, 9], "colores": ["Rojo", "Amarillo", "Verde"], "direccion": "Este"},
    "Tigre": {"numeros": [1, 3, 4], "colores": ["Gris", "Azul", "Naranja"], "direccion": "Noreste"},
    "Conejo": {"numeros": [3, 6, 9], "colores": ["Rojo", "Rosa", "Púrpura"], "direccion": "Este"},
    "Dragón": {"numeros": [1, 6, 7], "colores": ["Dorado", "Plateado", "Blanco"], "direccion": "Este"},
    "Serpiente": {"numeros": [2, 8, 9], "colores": ["Rojo", "Negro", "Amarillo"], "direccion": "Sur"},
    "Caballo": {"numeros": [2, 3, 7], "colores": ["Rojo", "Amarillo", "Verde"], "direccion": "Sur"},
    "Cabra": {"numeros": [2, 7], "colores": ["Rojo", "Azul", "Rosa"], "direccion": "Suroeste"},
    "Mono": {"numeros": [1, 7, 8], "colores": ["Blanco", "Dorado", "Azul"], "direccion": "Noroeste"},
    "Gallo": {"numeros": [5, 7, 8], "colores": ["Plateado", "Amarillo", "Dorado"], "direccion": "Oeste"},
    "Perro": {"numeros": [3, 4, 9], "colores": ["Rojo", "Verde", "Púrpura"], "direccion": "Este"},
    "Cerdo": {"numeros": [1, 3, 8], "colores": ["Amarillo", "Gris", "Marrón"], "direccion": "Norte"}
}

# Chinese New Year dates (1924-2043) for sign calculation
CHINESE_NEW_YEAR = [
    (1924, 2, 5), (1925, 1, 24), (1926, 2, 13), (1927, 2, 2), (1928, 1, 23), (1929, 2, 10),
    (1930, 1, 30), (1931, 2, 17), (1932, 2, 6), (1933, 1, 26), (1934, 2, 14), (1935, 2, 4),
    (1936, 1, 24), (1937, 2, 11), (1938, 1, 31), (1939, 2, 19), (1940, 2, 8), (1941, 1, 27),
    (1942, 2, 15), (1943, 2, 5), (1944, 1, 25), (1945, 2, 13), (1946, 2, 2), (1947, 1, 22),
    (1948, 2, 10), (1949, 1, 29), (1950, 2, 17), (1951, 2, 6), (1952, 1, 27), (1953, 2, 14),
    (1954, 2, 3), (1955, 1, 24), (1956, 2, 12), (1957, 1, 31), (1958, 2, 18), (1959, 2, 8),
    (1960, 1, 28), (1961, 2, 15), (1962, 2, 5), (1963, 1, 25), (1964, 2, 13), (1965, 2, 2),
    (1966, 1, 21), (1967, 2, 9), (1968, 1, 30), (1969, 2, 17), (1970, 2, 6), (1971, 1, 27),
    (1972, 2, 15), (1973, 2, 3), (1974, 1, 23), (1975, 2, 11), (1976, 1, 31), (1977, 2, 18),
    (1978, 2, 7), (1979, 1, 28), (1980, 2, 16), (1981, 2, 5), (1982, 1, 25), (1983, 2, 13),
    (1984, 2, 2), (1985, 2, 20), (1986, 2, 9), (1987, 1, 29), (1988, 2, 17), (1989, 2, 6),
    (1990, 1, 27), (1991, 2, 15), (1992, 2, 4), (1993, 1, 23), (1994, 2, 10), (1995, 1, 31),
    (1996, 2, 19), (1997, 2, 7), (1998, 1, 28), (1999, 2, 16), (2000, 2, 5), (2001, 1, 24),
    (2002, 2, 12), (2003, 2, 1), (2004, 1, 22), (2005, 2, 9), (2006, 1, 29), (2007, 2, 18),
    (2008, 2, 7), (2009, 1, 26), (2010, 2, 14), (2011, 2, 3), (2012, 1, 23), (2013, 2, 10),
    (2014, 1, 31), (2015, 2, 19), (2016, 2, 8), (2017, 1, 28), (2018, 2, 16), (2019, 2, 5),
    (2020, 1, 25), (2021, 2, 12), (2022, 2, 1), (2023, 1, 22), (2024, 2, 10), (2025, 1, 29),
    (2026, 2, 17), (2027, 2, 6), (2028, 1, 26), (2029, 2, 13), (2030, 2, 3), (2031, 1, 23),
    (2032, 2, 11), (2033, 1, 31), (2034, 2, 19), (2035, 2, 8), (2036, 1, 28), (2037, 2, 15),
    (2038, 2, 4), (2039, 1, 24), (2040, 2, 12), (2041, 2, 1), (2042, 1, 22), (2043, 2, 10),
]

def get_animal(birth_year: int) -> dict:
    idx = (birth_year - 4) % 12
    return ANIMALS[idx]

def get_element(birth_year: int) -> str:
    stem_idx = (birth_year - 4) % 10
    return ELEMENT_CYCLE[stem_idx]

def get_animal_by_birthday(year: int, month: int, day: int) -> dict:
    cny = None
    for y, m, d in CHINESE_NEW_YEAR:
        if y == year:
            cny = date(y, m, d)
            break
    if cny is None:
        return ANIMALS[(year - 4) % 12]
    birth = date(year, month, day)
    if birth < cny:
        year -= 1
    return ANIMALS[(year - 4) % 12]

def get_compatibility(a1: dict, a2: dict) -> dict:
    diff = abs(a1["id"] - a2["id"])
    if diff == 6:
        score = 20
        level = "Conflicto"
        desc = "Son signos opuestos. Tienden a chocar y tener perspectivas muy diferentes."
    elif a1["trine"] == a2["trine"]:
        score = 90
        level = "Excelente"
        desc = "Pertenecen al mismo tríada. Hay armonía natural y comprensión mutua."
    elif diff in (4, 8):
        score = 75
        level = "Buena"
        desc = "Hay atracción y respeto mutuo. Pueden construir una relación sólida."
    elif diff in (3, 9):
        score = 60
        level = "Neutral"
        desc = "Relación neutral. Con esfuerzo pueden entenderse bien."
    else:
        score = 45
        level = "Desafiante"
        desc = "Requiere trabajo y comprensión. Los opuestos pueden atraerse pero también generar fricción."
    return {"score": score, "level": level, "desc": desc}

# ── Database ──────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, password TEXT, nombre TEXT, animal TEXT NOT NULL DEFAULT '', birth_year INTEGER DEFAULT 0, signo TEXT DEFAULT '', premium INTEGER DEFAULT 0, notifications_enabled INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now')))")
        db.execute("CREATE TABLE IF NOT EXISTS horoscopes (animal TEXT, date TEXT, contenido TEXT, PRIMARY KEY (animal, date))")
        db.execute("CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER UNIQUE, paypal_subscription_id TEXT, status TEXT DEFAULT 'pending', plan TEXT DEFAULT 'monthly', current_period_start TEXT, current_period_end TEXT)")
        db.commit()

init_db()

# ── Auth ──────────────────────────────────────────────
def create_token(email):
    return jwt.encode({"email": email, "exp": datetime.now(TZ_ARG) + timedelta(days=30)}, JWT_SECRET, algorithm="HS256")

def get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Se requiere autenticación")
    try:
        data = jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
        return data["email"]
    except:
        raise HTTPException(401, "Token inválido")

# ── Static Files ──────────────────────────────────────
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"status": "ok", "app": "AstroChino"}

@app.get("/favicon.png")
async def favicon():
    if os.path.exists("favicon.png"):
        return FileResponse("favicon.png")
    raise HTTPException(404)

@app.get("/static/images/{filename}")
async def serve_image(filename: str):
    path = os.path.join("static/images", filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(404)

@app.get("/api/health")
async def health():
    return {"status": "ok", "llm_set": bool(LLM_API_KEY)}

# ── Auth Endpoints ────────────────────────────────────
class RegisterRequest(BaseModel):
    email: str
    password: str
    nombre: str
    birth_year: int
    birth_month: int = 1
    birth_day: int = 1

@app.post("/api/register")
async def register(req: RegisterRequest):
    animal = get_animal_by_birthday(req.birth_year, req.birth_month, req.birth_day)
    element = get_element(req.birth_year)
    hashed = hashlib.sha256(req.password.encode()).hexdigest()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO users (email, password, nombre, animal, birth_year, signo) VALUES (?, ?, ?, ?, ?, ?)",
                             (req.email, hashed, req.nombre, animal["name"], req.birth_year, f"{animal['name']} de {element}"))
            await db.commit()
    except:
        raise HTTPException(400, "El email ya está registrado")
    return {"success": True, "token": create_token(req.email), "animal": animal["name"], "element": element}

@app.post("/api/login")
async def login(req: RegisterRequest):
    hashed = hashlib.sha256(req.password.encode()).hexdigest()
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall("SELECT email, nombre, animal, premium, signo FROM users WHERE email=? AND password=?", (req.email, hashed))
        if not row:
            raise HTTPException(401, "Email o contraseña incorrectos")
        return {"success": True, "token": create_token(req.email), "nombre": row[0][1], "animal": row[0][2], "premium": row[0][3], "signo": row[0][4]}

@app.get("/api/profile")
async def profile(email: str = Depends(get_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall("SELECT email, nombre, animal, premium, notifications_enabled, signo, birth_year FROM users WHERE email=?", (email,))
        if not row:
            raise HTTPException(404, "Usuario no encontrado")
        return {"success": True, "user": {
            "email": row[0][0], "nombre": row[0][1], "animal": row[0][2],
            "premium": row[0][3], "notifications_enabled": row[0][4],
            "signo": row[0][5], "birth_year": row[0][6]
        }}

# ── Zodiac Endpoints ──────────────────────────────────
@app.get("/api/animals")
async def get_animals():
    return {"success": True, "animals": ANIMALS}

@app.get("/api/animal/{animal_name}")
async def get_animal_info(animal_name: str):
    animal = next((a for a in ANIMALS if a["name"].lower() == animal_name.lower()), None)
    if not animal:
        raise HTTPException(404, "Animal no encontrado")
    personality = PERSONALIDAD.get(animal["name"], "")
    lucky = LUCKY.get(animal["name"], {})
    return {"success": True, "animal": animal, "personality": personality, "lucky": lucky}

@app.get("/api/calculate")
async def calculate(year: int, month: int = 1, day: int = 1):
    animal = get_animal_by_birthday(year, month, day)
    element = get_element(year)
    personality = PERSONALIDAD.get(animal["name"], "")
    lucky = LUCKY.get(animal["name"], {})
    return {"success": True, "animal": animal, "element": element, "personality": personality, "lucky": lucky}

@app.get("/api/compatibility")
async def compatibility(animal1: str, animal2: str):
    a1 = next((a for a in ANIMALS if a["name"].lower() == animal1.lower() or a["name_en"].lower() == animal1.lower()), None)
    a2 = next((a for a in ANIMALS if a["name"].lower() == animal2.lower() or a["name_en"].lower() == animal2.lower()), None)
    if not a1 or not a2:
        raise HTTPException(404, "Animal no encontrado")
    comp = get_compatibility(a1, a2)
    return {"success": True, "animal1": a1, "animal2": a2, "compatibility": comp}

# ── Chinese Year Info ──────────────────────────────────
CNY_INFO = {
    "year": 2026,
    "chinese_year": 4724,
    "animal": "Caballo",
    "element": "Fuego",
    "yin_yang": "Yang",
    "name_cn": "丙午",
    "start_date": "17 de Febrero, 2026",
    "end_date": "5 de Febrero, 2027",
    "description": "El Año del Caballo de Fuego (丙午) es un año de acción, pasión y movimiento. El fuego alimenta la energía del Caballo, creando un período de gran dinamismo, impulsividad y transformación. Es un año para tomar riesgos calculados, perseguir metas con determinación y expresar la verdad sin miedo. La energía Yang del Caballo de Fuego favorece el liderazgo, la aventura y la expansión personal.",
    "element_description": "El Fuego (火) representa la pasión, la creatividad y la transformación. Los años de Fuego son intensos, llenos de energía y cambios repentinos.",
    "advice": "Aprovechá la energía del Caballo de Fuego para avanzar en tus proyectos, pero evitá decisiones impulsivas. Canalizá tu pasión con disciplina."
}

@app.get("/api/year-info")
async def year_info():
    return {"success": True, "info": CNY_INFO}

# ── Horoscope ─────────────────────────────────────────
PERIOD_LABELS = {"today": "hoy", "tomorrow": "mañana", "weekly": "esta semana", "monthly": "este mes", "yearly": "este año"}

async def generate_horoscope(animal_name: str, period: str = "today") -> str:
    animal = next(a for a in ANIMALS if a["name"] == animal_name)
    lucky = LUCKY.get(animal_name, {})
    now = datetime.now(TZ_ARG)
    period_label = PERIOD_LABELS.get(period, "hoy")
    date_str = now.strftime("%d/%m/%Y")
    prompts = {
        "today": f"Eres un astrólogo chino experto. Genera un horóscopo para {animal_name} ({animal['name_en']}) del {date_str} en español (máx 100 palabras). Incluye energía general del día, un aspecto destacado (amor/trabajo/salud), números de la suerte {lucky.get('numeros', [])} y el color del día. Texto plano.",
        "tomorrow": f"Eres un astrólogo chino experto. Genera una predicción para {animal_name} ({animal['name_en']}) para MAÑANA {date_str} en español (máx 100 palabras). Incluye lo que se viene, oportunidades, precauciones y números de la suerte {lucky.get('numeros', [])}. Texto plano.",
        "weekly": f"Eres un astrólogo chino experto. Genera un horóscopo SEMANAL para {animal_name} ({animal['name_en']}) en español (máx 120 palabras). Incluye tendencias generales de la semana, aspectos destacados en amor, trabajo y salud, y números de la suerte {lucky.get('numeros', [])}. Texto plano.",
        "monthly": f"Eres un astrólogo chino experto. Genera un horóscopo MENSUAL para {animal_name} ({animal['name_en']}) en español (máx 150 palabras). Incluye panorama general del mes, predicciones por áreas (amor, trabajo, dinero, salud) y números de la suerte {lucky.get('numeros', [])}. Texto plano.",
        "yearly": f"Eres un astrólogo chino experto. Genera un horóscopo ANUAL 2026 para {animal_name} ({animal['name_en']}) en español (máx 200 palabras). Incluye predicciones generales para el año, oportunidades, desafíos y consejos. Texto plano.",
    }
    prompt = prompts.get(period, prompts["today"])
    if LLM_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={LLM_API_KEY}"
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(url, json={"contents":[{"parts":[{"text":prompt}]}]})
                if r.status_code == 200:
                    data = r.json()
                    text = data.get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","")
                    if text: return text.strip()
        except:
            pass
    return _fallback_horoscope(animal_name, period)

def _fallback_horoscope(animal_name: str, period: str = "today") -> str:
    lucky = LUCKY.get(animal_name, {})
    colores = lucky.get('colores', ['Rojo'])
    numeros = lucky.get('numeros', [7])
    period_label = PERIOD_LABELS.get(period, "hoy")
    if period == "tomorrow":
        return f"📅 Predicción para mañana de {animal_name}:\n\nLa energía se renueva. Mañana será un día para observar antes de actuar. Prestá atención a las señales del entorno.\n\n🔮 Consejo: Alguien cercano可能需要 tu ayuda. Estate atento.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}."
    elif period == "weekly":
        return f"📆 Horóscopo semanal para {animal_name}:\n\nEsta semana trae oportunidades de crecimiento. La energía del {CNY_INFO['animal']} de {CNY_INFO['element']} te impulsa a tomar la iniciativa.\n\n❤️ Amor: Buen momento para conversaciones profundas.\n💼 Trabajo: Avances en proyectos pendientes.\n💪 Salud: Mantené rutinas saludables.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}."
    elif period == "monthly":
        return f"📅 Horóscopo mensual para {animal_name}:\n\nPanorama general: Un mes de transformación. La energía del {CNY_INFO['element']} te invita a soltar lo que ya no sirve.\n\n❤️ Amor: Relaciones se profundizan. Buena época para compromisos.\n💼 Trabajo: Nuevas oportunidades profesionales.\n💰 Dinero: Mes estable, evitá gastos impulsivos.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}."
    elif period == "yearly":
        return f"🗓️ Horóscopo anual 2026 para {animal_name}:\n\nEl Año del Caballo de Fuego trae cambios dinámicos para {animal_name}. Es un año de acción y determinación.\n\n✨ Oportunidades: Grandes avances en carrera y proyectos personales.\n⚠️ Desafíos: Evitá la impulsividad. Pensá antes de actuar.\n💕 Amor: Los solteros encontrarán conexiones significativas.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}."
    plantillas = [
        f"⚡ Energía general: Hoy {animal_name} siente una corriente de renovación. Es un día para tomar decisiones con claridad.\n\n❤️ Amor: Las relaciones se profundizan si dedicás tiempo de calidad.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}.",
        f"🌅 Mañana prometedora para {animal_name}. Mantené el foco en tus metas.\n\n💼 Trabajo: Momento de colaborar. Compartir ideas te abrirá puertas.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}.",
        f"🌀 {animal_name}, hoy la clave está en el equilibrio. Observá antes de actuar.\n\n💪 Salud: Tu energía física está alta. Aprovechá para moverte.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}.",
        f"✨ Día de claridad para {animal_name}. Las nubes se disipan y ves el camino con nitidez.\n\n🔮 Consejo: Algo que venías postergando encuentra su momento.\n\n🍀 Suerte: Números {numeros}, Color: {random.choice(colores)}.",
    ]
    return random.choice(plantillas)

@app.get("/api/horoscope/{animal_name}")
async def get_horoscope(animal_name: str, period: str = "today"):
    animal = next((a for a in ANIMALS if a["name"].lower() == animal_name.lower()), None)
    if not animal:
        raise HTTPException(404, "Animal no encontrado")
    if period not in PERIOD_LABELS:
        period = "today"
    today = datetime.now(TZ_ARG).strftime("%Y-%m-%d")
    cache_key = f"{animal['name']}_{period}_{today}"
    # For non-daily periods, use a weekly/monthly key
    if period == "weekly":
        week_start = datetime.now(TZ_ARG).strftime("%Y-W%W")
        cache_key = f"{animal['name']}_{period}_{week_start}"
    elif period == "monthly":
        cache_key = f"{animal['name']}_{period}_{datetime.now(TZ_ARG).strftime('%Y-%m')}"
    elif period == "yearly":
        cache_key = f"{animal['name']}_{period}_2026"
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall("SELECT contenido FROM horoscopes WHERE animal=? AND date=?", (animal["name"], cache_key))
        if row:
            content = row[0][0]
        else:
            content = await generate_horoscope(animal["name"], period)
            await db.execute("INSERT OR REPLACE INTO horoscopes (animal, date, contenido) VALUES (?, ?, ?)", (animal["name"], cache_key, content))
            await db.commit()
    lucky = LUCKY.get(animal["name"], {})
    return {"success": True, "animal": animal["name"], "date": today, "period": period, "horoscope": content, "lucky": lucky}

# ── Premium (PayPal) ─────────────────────────────
@app.post("/api/set-premium")
async def set_premium(email: str = Depends(get_user)):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET premium=1 WHERE email=?", (email,))
        await db.commit()
    return {"success": True}

# ── PayPal Helpers ───────────────────────────────────────
async def _paypal_token() -> str:
    global _paypal_cached_token, _paypal_cached_token_expires
    if _paypal_cached_token and datetime.utcnow().timestamp() < _paypal_cached_token_expires - 60:
        return _paypal_cached_token
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(503, "PayPal no está configurado")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{PAYPAL_BASE}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        _paypal_cached_token = data["access_token"]
        _paypal_cached_token_expires = datetime.utcnow().timestamp() + data.get("expires_in", 32400)
        return _paypal_cached_token

async def _paypal_create_product() -> str:
    token = await _paypal_token()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{PAYPAL_BASE}/v1/catalogs/products",
            json={"name": "AstroChino Premium", "description": "Suscripción premium a AstroChino", "type": "SERVICE", "category": "SOFTWARE"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        if r.status_code == 409:
            return ""
        r.raise_for_status()
        return r.json()["id"]

async def _paypal_find_or_create_plan() -> str:
    if PREMIUM_PLAN_ID:
        return PREMIUM_PLAN_ID
    token = await _paypal_token()
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{PAYPAL_BASE}/v1/billing/plans",
            params={"page_size": 20, "status": "ACTIVE"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        if r.status_code == 200:
            for p in r.json().get("plans", []):
                if p["name"] == "Premium Mensual $2":
                    return p["id"]
        prod_id = await _paypal_create_product()
        if not prod_id:
            raise HTTPException(503, "Error creando producto PayPal")
        r2 = await client.post(
            f"{PAYPAL_BASE}/v1/billing/plans",
            json={
                "product_id": prod_id,
                "name": "Premium Mensual $2",
                "description": "Acceso premium a todas las funcionalidades",
                "billing_cycles": [{"frequency": {"interval_unit": "MONTH", "interval_count": 1}, "tenure_type": "REGULAR", "sequence": 1, "total_cycles": 0, "pricing_scheme": {"fixed_price": {"value": "2.00", "currency_code": "USD"}}}],
                "payment_preferences": {"auto_bill_outstanding": True, "setup_fee_failure_action": "CONTINUE", "payment_failure_threshold": 3},
            },
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        r2.raise_for_status()
        return r2.json()["id"]

async def _paypal_verify_webhook(headers: dict, body: bytes) -> dict:
    token = await _paypal_token()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{PAYPAL_BASE}/v1/notifications/verify-webhook-signature",
            json={
                "auth_algo": headers.get("paypal-auth-algo", ""),
                "cert_url": headers.get("paypal-cert-url", ""),
                "transmission_id": headers.get("paypal-transmission-id", ""),
                "transmission_sig": headers.get("paypal-transmission-sig", ""),
                "transmission_time": headers.get("paypal-transmission-time", ""),
                "webhook_id": PAYPAL_WEBHOOK_ID,
                "webhook_event": json.loads(body),
            },
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()

@app.post("/api/subscription/create-checkout")
async def create_checkout(user_email: str = Depends(get_user)):
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        raise HTTPException(503, "PayPal no está configurado. Contactá al administrador.")
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute_fetchall("SELECT id FROM users WHERE email=?", (user_email,))
        if not row:
            raise HTTPException(404, "Usuario no encontrado")
        uid = row[0][0]
    try:
        plan_id = await _paypal_find_or_create_plan()
        token = await _paypal_token()
        return_url = "https://astrochino.onrender.com/?premium=success"
        cancel_url = "https://astrochino.onrender.com/?premium=cancel"
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{PAYPAL_BASE}/v1/billing/subscriptions",
                json={
                    "plan_id": plan_id,
                    "custom_id": str(uid),
                    "application_context": {
                        "brand_name": "AstroChino",
                        "locale": "es-AR",
                        "shipping_preference": "NO_SHIPPING",
                        "user_action": "SUBSCRIBE_NOW",
                        "payment_method": {"payer_selected": "PAYPAL", "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED"},
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    },
                    "subscriber": {"email_address": user_email},
                },
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
            )
            r.raise_for_status()
            sub = r.json()
            approval_url = next((l["href"] for l in sub.get("links", []) if l["rel"] == "approve"), None)
            if not approval_url:
                raise HTTPException(500, "No se pudo obtener la URL de aprobación de PayPal")
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO subscriptions (user_id, paypal_subscription_id, status) VALUES (?, ?, ?)", (uid, sub["id"], "pending"))
                await db.commit()
        return {"success": True, "url": approval_url}
    except Exception as e:
        raise HTTPException(500, f"Error al crear la suscripción en PayPal: {e}")

@app.post("/api/webhook/paypal")
async def paypal_webhook(request: Request):
    if not PAYPAL_WEBHOOK_ID:
        raise HTTPException(503, "Webhook PayPal no configurado")
    payload = await request.body()
    headers_dict = {k.lower(): v for k, v in request.headers.items()}
    try:
        verification = await _paypal_verify_webhook(headers_dict, payload)
        if verification.get("verification_status") != "SUCCESS":
            raise HTTPException(400, "Firma de webhook inválida")
    except Exception as e:
        raise HTTPException(400, f"Error verificando webhook: {e}")
    event = json.loads(payload)
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    if event_type == "PAYMENT.SALE.COMPLETED":
        sub_id = resource.get("billing_agreement_id") or resource.get("subscription_id", "")
        if sub_id:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM subscriptions WHERE paypal_subscription_id = ?", (sub_id,))
                row = await cur.fetchone()
                if row:
                    await db.execute("UPDATE users SET premium = 1 WHERE id = ?", (row["user_id"],))
                    await db.execute("UPDATE subscriptions SET status = 'active', current_period_start = datetime('now'), current_period_end = datetime('now', '+1 month') WHERE paypal_subscription_id = ?", (sub_id,))
                    await db.commit()
    elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED"):
        sub_id = resource.get("id", "")
        if sub_id:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT user_id FROM subscriptions WHERE paypal_subscription_id = ?", (sub_id,))
                row = await cur.fetchone()
                if row:
                    await db.execute("UPDATE users SET premium = 0 WHERE id = ?", (row["user_id"],))
                    await db.execute("UPDATE subscriptions SET status = 'canceled' WHERE paypal_subscription_id = ?", (sub_id,))
                    await db.commit()
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
