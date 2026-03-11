from flask import Flask, request, jsonify
from flask_cors import CORS  # <--- 1. Agregamos la importación
import swisseph as swe

app = Flask(__name__)
CORS(app)  # <--- 2. Habilitamos CORS para toda la app

def calcular_carta_ultra_precisa(año, mes, dia, hora_local, minuto, lat, lon, offset_utc):
    swe.set_ephe_path('')
    hora_utc_decimal = (hora_local + (minuto / 60.0)) - offset_utc
    jd = swe.julday(año, mes, dia, hora_utc_decimal, swe.GREG_CAL)
    
    planetas = {
        'Sol': swe.SUN, 'Luna': swe.MOON, 'Mercurio': swe.MERCURY, 
        'Venus': swe.VENUS, 'Marte': swe.MARS, 'Júpiter': swe.JUPITER, 
        'Saturno': swe.SATURN, 'Urano': swe.URANUS, 'Neptuno': swe.NEPTUNE, 
        'Plutón': swe.PLUTO
    }
    
    zodiaco = ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", 
               "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"]

    def formatear_grados(longitud_ecliptica):
        signo_idx = int(longitud_ecliptica / 30)
        grados_puros = longitud_ecliptica % 30
        g = int(grados_puros)
        minutos_dec = (grados_puros - g) * 60
        m = int(minutos_dec)
        segundos_dec = (minutos_dec - m) * 60
        s = int(round(segundos_dec))
        
        if s == 60: s = 0; m += 1
        if m == 60: m = 0; g += 1
        if g == 30: g = 0; signo_idx = (signo_idx + 1) % 12
            
        return f"{zodiaco[signo_idx]} {g:02d}°{m:02d}'{s:02d}\""

    resultados = {}
    for nombre, id_planeta in planetas.items():
        pos, ret = swe.calc_ut(jd, id_planeta, swe.FLG_SWIEPH)
        longitud = pos[0]
        velocidad = pos[3]
        estado = " Rx" if velocidad < 0 else ""
        resultados[nombre] = formatear_grados(longitud) + estado

    casas, asmc = swe.houses_ex(jd, lat, lon, b'P')
    resultados['Ascendente'] = formatear_grados(asmc[0])

    return resultados

@app.route('/calcular', methods=['GET'])
def calcular():
    try:
        # Nota: Si el agente tiene problemas con la 'ñ', podrías cambiar esto a 'anio'
        año = int(request.args.get('año'))
        mes = int(request.args.get('mes'))
        dia = int(request.args.get('dia'))
        hora = int(request.args.get('hora'))
        minuto = int(request.args.get('minuto'))
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        offset = float(request.args.get('offset'))
        
        carta = calcular_carta_ultra_precisa(año, mes, dia, hora, minuto, lat, lon, offset)
        return jsonify(carta)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
