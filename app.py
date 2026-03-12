from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe

app = Flask(__name__)
CORS(app)

# --- CONSTANTES ASTROLÓGICAS ---
ZODIACO = ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", 
           "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"]

ELEMENTOS = {
    "Aries": "Fuego", "Leo": "Fuego", "Sagitario": "Fuego",
    "Tauro": "Tierra", "Virgo": "Tierra", "Capricornio": "Tierra",
    "Géminis": "Aire", "Libra": "Aire", "Acuario": "Aire",
    "Cáncer": "Agua", "Escorpio": "Agua", "Piscis": "Agua"
}

MODALIDADES = {
    "Aries": "Cardinal", "Cáncer": "Cardinal", "Libra": "Cardinal", "Capricornio": "Cardinal",
    "Tauro": "Fijo", "Leo": "Fijo", "Escorpio": "Fijo", "Acuario": "Fijo",
    "Géminis": "Mutable", "Virgo": "Mutable", "Sagitario": "Mutable", "Piscis": "Mutable"
}

# Dignidades: {Planeta: {'Domicilio': [Signos], 'Exaltación': Signo, 'Caída': Signo, 'Exilio': [Signos]}}
DIGNIDADES_MAP = {
    'Sol': {'Dom': ['Leo'], 'Exa': 'Aries', 'Cai': 'Libra', 'Exi': ['Acuario']},
    'Luna': {'Dom': ['Cáncer'], 'Exa': 'Tauro', 'Cai': 'Escorpio', 'Exi': ['Capricornio']},
    'Mercurio': {'Dom': ['Géminis', 'Virgo'], 'Exa': 'Virgo', 'Cai': 'Piscis', 'Exi': ['Sagitario', 'Piscis']},
    'Venus': {'Dom': ['Tauro', 'Libra'], 'Exa': 'Piscis', 'Cai': 'Virgo', 'Exi': ['Aries', 'Escorpio']},
    'Marte': {'Dom': ['Aries', 'Escorpio'], 'Exa': 'Capricornio', 'Cai': 'Cáncer', 'Exi': ['Libra', 'Tauro']},
    'Júpiter': {'Dom': ['Sagitario', 'Piscis'], 'Exa': 'Cáncer', 'Cai': 'Capricornio', 'Exi': ['Géminis', 'Virgo']},
    'Saturno': {'Dom': ['Capricornio', 'Acuario'], 'Exa': 'Libra', 'Cai': 'Aries', 'Exi': ['Cáncer', 'Leo']}
}

# --- FUNCIONES DE APOYO ---

def get_dignidad(planeta, signo):
    if planeta not in DIGNIDADES_MAP: return "Neutral"
    d = DIGNIDADES_MAP[planeta]
    if signo in d['Dom']: return "Domicilio"
    if signo == d['Exa']: return "Exaltación"
    if signo == d['Cai']: return "Caída"
    if signo in d['Exi']: return "Exilio"
    return "Neutral"

def formatear_pos(longitud):
    idx = int(longitud / 30)
    g = int(longitud % 30)
    m = int((longitud % 1) * 60)
    return ZODIACO[idx], f"{ZODIACO[idx]} {g:02d}°{m:02d}'"

def calcular_aspectos(posiciones):
    # Aspectos mayores y sus orbes permitidos
    tipos_aspectos = {0: ("Conjunción", 8), 180: ("Oposición", 8), 120: ("Trígono", 8), 90: ("Cuadratura", 7), 60: ("Sextil", 5)}
    encontrados = []
    nombres = list(posiciones.keys())
    
    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            p1, p2 = nombres[i], nombres[j]
            # No calcular aspectos con casas o nodos para no saturar, o filtrar según preferencia
            if "Casa" in p1 or "Casa" in p2: continue
            
            diff = abs(posiciones[p1]['long'] - posiciones[p2]['long'])
            if diff > 180: diff = 360 - diff
            
            for angulo, (tipo, orbe) in tipos_aspectos.items():
                distancia_al_aspecto = abs(diff - angulo)
                if distancia_al_aspecto <= orbe:
                    encontrados.append({
                        "p1": p1, "p2": p2, "tipo": tipo, "orbe": round(distancia_al_aspecto, 2)
                    })
    return encontrados

# --- LÓGICA PRINCIPAL ---

def generar_reporte_astrologico(año, mes, dia, hora, minuto, lat, lon, offset):
    swe.set_ephe_path('')
    jd = swe.julday(año, mes, dia, (hora + minuto/60.0) - offset, swe.GREG_CAL)
    
    planetas_ids = {
        'Sol': swe.SUN, 'Luna': swe.MOON, 'Mercurio': swe.MERCURY, 'Venus': swe.VENUS,
        'Marte': swe.MARS, 'Júpiter': swe.JUPITER, 'Saturno': swe.SATURN,
        'Urano': swe.URANUS, 'Neptuno': swe.NEPTUNE, 'Plutón': swe.PLUTO, 'Nodo Norte': swe.MEAN_NODE
    }

    raw_data = {}
    balance = {"Elementos": {"Fuego": 0, "Tierra": 0, "Aire": 0, "Agua": 0}, 
               "Modalidades": {"Cardinal": 0, "Fijo": 0, "Mutable": 0}}

    # 1. Posiciones y Dignidades
    for nombre, pid in planetas_ids.items():
        pos, ret = swe.calc_ut(jd, pid, swe.FLG_SWIEPH)
        signo, legible = formatear_pos(pos[0])
        rx = " (Rx)" if pos[3] < 0 else ""
        
        raw_data[nombre] = {
            "posicion": legible + rx,
            "long": pos[0],
            "signo": signo,
            "dignidad": get_dignidad(nombre, signo),
            "retrogrado": pos[3] < 0
        }
        
        # Balance (solo planetas, no nodos)
        if nombre != 'Nodo Norte':
            balance["Elementos"][ELEMENTOS[signo]] += 1
            balance["Modalidades"][MODALIDADES[signo]] += 1

    # 2. Casas
    casas, asmc = swe.houses_ex(jd, lat, lon, b'P')
    raw_data['Ascendente'] = {"posicion": formatear_pos(asmc[0])[1], "long": asmc[0]}
    raw_data['Medio Cielo'] = {"posicion": formatear_pos(asmc[1])[1], "long": asmc[1]}
    
    for i in range(12):
        raw_data[f'Casa {i+1}'] = {"posicion": formatear_pos(casas[i])[1], "long": casas[i]}

    # 3. Aspectos
    aspectos = calcular_aspectos(raw_data)

    return {
        "puntos_celestes": {k: v['posicion'] for k, v in raw_data.items() if 'posicion' in v},
        "dignidades": {k: v['dignidad'] for k, v in raw_data.items() if 'dignidad' in v},
        "aspectos": aspectos,
        "balance_energetico": balance
    }

@app.route('/calcular', methods=['GET'])
def calcular():
    try:
        a = request.args
        res = generar_reporte_astrologico(
            int(a.get('año')), int(a.get('mes')), int(a.get('dia')),
            int(a.get('hora')), int(a.get('minuto')),
            float(a.get('lat')), float(a.get('lon')), float(a.get('offset'))
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
