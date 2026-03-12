from flask import Flask, request, jsonify
from flask_cors import CORS
import swisseph as swe

app = Flask(__name__)
CORS(app)

# --- CONFIGURACIÓN Y TABLAS DE REFERENCIA ---

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

# Dignidades tradicionales
DIGNIDADES_MAP = {
    'Sol': {'Dom': ['Leo'], 'Exa': 'Aries', 'Cai': 'Libra', 'Exi': ['Acuario']},
    'Luna': {'Dom': ['Cáncer'], 'Exa': 'Tauro', 'Cai': 'Escorpio', 'Exi': ['Capricornio']},
    'Mercurio': {'Dom': ['Géminis', 'Virgo'], 'Exa': 'Virgo', 'Cai': 'Piscis', 'Exi': ['Sagitario', 'Piscis']},
    'Venus': {'Dom': ['Tauro', 'Libra'], 'Exa': 'Piscis', 'Cai': 'Virgo', 'Exi': ['Aries', 'Escorpio']},
    'Marte': {'Dom': ['Aries', 'Escorpio'], 'Exa': 'Capricornio', 'Cai': 'Cáncer', 'Exi': ['Libra', 'Tauro']},
    'Júpiter': {'Dom': ['Sagitario', 'Piscis'], 'Exa': 'Cáncer', 'Cai': 'Capricornio', 'Exi': ['Géminis', 'Virgo']},
    'Saturno': {'Dom': ['Capricornio', 'Acuario'], 'Exa': 'Libra', 'Cai': 'Aries', 'Exi': ['Cáncer', 'Leo']}
}

# --- FUNCIONES AUXILIARES ---

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
    s = int(((longitud % 1) * 60 % 1) * 60)
    return ZODIACO[idx], f"{ZODIACO[idx]} {g:02d}°{m:02d}'{s:02d}\""

def calcular_aspectos(posiciones):
    # Tipos de aspectos: (Ángulo, Orbe permitido)
    tipos = {0: ("Conjunción", 8), 180: ("Oposición", 8), 120: ("Trígono", 8), 90: ("Cuadratura", 7), 60: ("Sextil", 5)}
    encontrados = []
    nombres = [n for n in posiciones.keys() if "Casa" not in n and n not in ["Ascendente", "Medio Cielo"]]
    
    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            p1, p2 = nombres[i], nombres[j]
            diff = abs(posiciones[p1]['long'] - posiciones[p2]['long'])
            if diff > 180: diff = 360 - diff
            
            for angulo, (tipo, max_orbe) in tipos.items():
                orbe_actual = abs(diff - angulo)
                if orbe_actual <= max_orbe:
                    encontrados.append({
                        "p1": p1, "p2": p2, "tipo": tipo, "orbe": round(orbe_actual, 2)
                    })
    return encontrados

# --- LÓGICA CORE ---

def generar_analisis_completo(año, mes, dia, hora, minuto, lat, lon, offset):
    swe.set_ephe_path('') # Usa efemérides integradas (1900-2050)
    
    # Cálculo del Julian Day
    hora_utc = (hora + minuto/60.0) - offset
    jd = swe.julday(año, mes, dia, hora_utc, swe.GREG_CAL)
    
    planetas_ids = {
        'Sol': swe.SUN, 'Luna': swe.MOON, 'Mercurio': swe.MERCURY, 'Venus': swe.VENUS,
        'Marte': swe.MARS, 'Júpiter': swe.JUPITER, 'Saturno': swe.SATURN,
        'Urano': swe.URANUS, 'Neptuno': swe.NEPTUNE, 'Plutón': swe.PLUTO, 'Nodo Norte': swe.MEAN_NODE
    }

    datos_crudos = {}
    balance = {"Elementos": {"Fuego": 0, "Tierra": 0, "Aire": 0, "Agua": 0}, 
               "Modalidades": {"Cardinal": 0, "Fijo": 0, "Mutable": 0}}

    # 1. Posiciones, Dignidades y Balance
    for nombre, pid in planetas_ids.items():
        res, ret = swe.calc_ut(jd, pid, swe.FLG_SWIEPH)
        longitud = res[0]
        velocidad = res[3]
        signo, legible = formatear_pos(longitud)
        rx = " (Rx)" if velocidad < 0 else ""
        
        datos_crudos[nombre] = {
            "posicion": legible + rx,
            "long": longitud,
            "signo": signo,
            "dignidad": get_dignidad(nombre, signo)
        }
        
        # El balance energético suele excluir a los Nodos
        if nombre != 'Nodo Norte':
            balance["Elementos"][ELEMENTOS[signo]] += 1
            balance["Modalidades"][MODALIDADES[signo]] += 1

    # 2. Casas y Ángulos
    casas, asmc = swe.houses_ex(jd, lat, lon, b'P')
    datos_crudos['Ascendente'] = {"posicion": formatear_pos(asmc[0])[1], "long": asmc[0]}
    datos_crudos['Medio Cielo'] = {"posicion": formatear_pos(asmc[1])[1], "long": asmc[1]}
    for i in range(12):
        datos_crudos[f'Casa {i+1}'] = {"posicion": formatear_pos(casas[i])[1], "long": casas[i]}

    # 3. Cálculo de Aspectos
    aspectos_lista = calcular_aspectos(datos_crudos)

    # 4. Construcción del JSON Final
    return {
        "puntos_celestes": {k: v['posicion'] for k, v in datos_crudos.items()},
        "dignidades": {k: v['dignidad'] for k, v in datos_crudos.items() if 'dignidad' in v},
        "aspectos": aspectos_lista,
        "balance_energetico": balance
    }

# --- RUTAS FLASK ---

@app.route('/calcular', methods=['GET'])
def calcular():
    try:
        # Usamos .get() para evitar errores si falta algún parámetro
        args = request.args
        resultado = generar_analisis_completo(
            int(args.get('año')), int(args.get('mes')), int(args.get('dia')),
            int(args.get('hora')), int(args.get('minuto')),
            float(args.get('lat')), float(args.get('lon')), float(args.get('offset'))
        )
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": f"Error en los parámetros o en el cálculo: {str(e)}"}), 400

if __name__ == '__main__':
    # Puerto 10000 es el estándar de Render
    app.run(host='0.0.0.0', port=10000)
