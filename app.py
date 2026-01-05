import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
import urllib.parse
import urllib.request
import json
import random
import math
import re
import pydeck as pdk
from streamlit_autorefresh import st_autorefresh
import io
import base64
from PIL import Image

# --- ⚙️ CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="TAXI SEGURO", page_icon="🚖", layout="centered")

SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"
LAT_BASE, LON_BASE = -0.466657, -76.989635

# Inicialización de estados
if 'viaje_confirmado' not in st.session_state: 
    st.session_state.viaje_confirmado = False
if 'datos_pedido' not in st.session_state: 
    st.session_state.datos_pedido = {}
if 'gps_ready' not in st.session_state:
    st.session_state.gps_ready = False
if 'ultima_lat' not in st.session_state:
    st.session_state.ultima_lat = None
if 'ultima_lon' not in st.session_state:
    st.session_state.ultima_lon = None
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# --- DESACTIVAR AUTO-REFRESH EN MODO DEBUG ---
# Solo refresca si NO está en debug y NO hay viaje confirmado
if not st.session_state.debug_mode and not st.session_state.viaje_confirmado:
    st_autorefresh(interval=5000, key="gps_refresh")

# 🎨 ESTILOS CSS
st.markdown("""
    <style>
    .main-title { font-size: 40px; font-weight: bold; text-align: center; color: #000; margin-bottom: 0; }
    .sub-title { font-size: 25px; font-weight: bold; text-align: center; color: #E91E63; margin-top: -10px; margin-bottom: 20px; }
    .step-header { font-size: 18px; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #333; }
    .stButton>button { width: 100%; height: 50px; font-weight: bold; font-size: 18px; border-radius: 10px; }
    .id-badge { background-color: #F0F2F6; padding: 5px 15px; border-radius: 20px; border: 1px solid #CCC; font-weight: bold; color: #555; display: inline-block; margin-bottom: 10px; }
    .eta-box { background-color: #FFF3E0; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; text-align: center; margin-bottom: 15px; font-weight: bold; }
    .footer { text-align: center; color: #888; font-size: 14px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }
    .gps-status { background: linear-gradient(90deg, #4CAF50, #8BC34A); color: white; padding: 10px; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 🛠️ FUNCIONES ---

def calcular_distancia_real(lat1, lon1, lat2, lon2):
    """Calcula la distancia en KM entre dos puntos."""
    try:
        R = 6371
        dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)) * R
    except: 
        return 0.0

def obtener_ruta_carretera(lon1, lat1, lon2, lat2):
    """Consulta OSRM para trazar el camino por las calles."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        with urllib.request.urlopen(url, timeout=4) as response:
            data = json.loads(response.read().decode())
            return [{"path": data['routes'][0]['geometry']['coordinates']}]
    except:
        return [{"path": [[lon1, lat1], [lon2, lat2]]}]

def cargar_datos(hoja):
    try:
        cb = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cb}"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.upper()
        return df
    except: 
        return pd.DataFrame()

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_completa = f"{URL_SCRIPT}?{params}"
        
        # Crear request con headers
        req = urllib.request.Request(url_completa)
        req.add_header('User-Agent', 'Mozilla/5.0')
        
        with urllib.request.urlopen(req, timeout=15) as response:
            resultado = response.read().decode('utf-8')
            return resultado if resultado else "OK"
    except urllib.error.URLError as e:
        return f"Error de conexión: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

def obtener_chofer_mas_cercano(lat_cli, lon_cli, tipo_sol):
    st.write("="*50)
    st.write("🔍 INICIANDO BÚSQUEDA DE CONDUCTOR")
    st.write("="*50)
    
    df_c = cargar_datos("CHOFERES")
    df_u = cargar_datos("UBICACIONES")
    
    st.write(f"📊 CHOFERES cargados: {len(df_c)} filas")
    st.write(f"📍 UBICACIONES cargadas: {len(df_u)} filas")
    
    if df_c.empty:
        st.error("❌ Hoja CHOFERES está vacía")
        return None, None, None, "S/P"
    
    if df_u.empty:
        st.error("❌ Hoja UBICACIONES está vacía")
        return None, None, None, "S/P"
    
    # Mostrar columnas
    st.write("📋 Columnas en CHOFERES:")
    st.write(df_c.columns.tolist())
    st.write("📋 Columnas en UBICACIONES:")
    st.write(df_u.columns.tolist())
    
    # Mostrar TODOS los datos de CHOFERES
    st.write("👥 DATOS COMPLETOS DE CHOFERES:")
    st.dataframe(df_c)
    
    # Verificar columna ESTADO
    if 'ESTADO' not in df_c.columns:
        st.error("❌ NO existe columna ESTADO")
        return None, None, None, "Error Cols"
    
    st.write(f"📊 Estados en CHOFERES: {df_c['ESTADO'].unique()}")
    
    # Mostrar cada conductor y su estado
    for idx, row in df_c.iterrows():
        nombre = f"{row.get('NOMBRE', '')} {row.get('APELLIDO', '')}"
        estado = row.get('ESTADO', 'SIN ESTADO')
        st.write(f"  - {nombre}: Estado = '{estado}' (tipo: {type(estado)})")
    
    tipo_b = tipo_sol.split(" ")[0].upper()
    st.write(f"🔎 Buscando tipo: **{tipo_b}**")

    # FILTRO 1: Solo conductores LIBRES
    st.write("🔍 Aplicando filtro ESTADO == LIBRE...")
    libres = df_c[df_c['ESTADO'].astype(str).str.upper().str.strip() == 'LIBRE']
    
    st.write(f"✅ Conductores con ESTADO=LIBRE: **{len(libres)}**")
    
    if len(libres) == 0:
        st.error("❌ NO HAY CONDUCTORES LIBRES")
        st.write("Intentando con estados diferentes...")
        
        # Mostrar qué estados hay
        for estado_unico in df_c['ESTADO'].unique():
            count = len(df_c[df_c['ESTADO'] == estado_unico])
            st.write(f"  - Estado '{estado_unico}': {count} conductores")
        
        # MODO EMERGENCIA: Aceptar CUALQUIER estado
        st.warning("⚠️ MODO EMERGENCIA: Aceptando TODOS los estados")
        libres = df_c.copy()
    
    # FILTRO 2: Tipo de vehículo
    if 'TIPO_VEHICULO' in libres.columns:
        st.write(f"🚗 Tipos disponibles: {libres['TIPO_VEHICULO'].unique()}")
        
        antes = len(libres)
        libres = libres[libres['TIPO_VEHICULO'].astype(str).str.upper().str.contains(tipo_b, na=False)]
        st.write(f"Después de filtro tipo {tipo_b}: {len(libres)} (eliminados: {antes - len(libres)})")
        
        if len(libres) == 0:
            st.error(f"❌ No hay conductores tipo {tipo_b}")
            st.warning("Aceptando CUALQUIER tipo de vehículo")
            libres = df_c.copy()
    else:
        st.warning("⚠️ No existe TIPO_VEHICULO")

    # FILTRO 3: Deuda
    if 'DEUDA' in libres.columns:
        antes = len(libres)
        libres = libres[pd.to_numeric(libres['DEUDA'], errors='coerce').fillna(0) < 10.00]
        st.write(f"Después de filtro deuda: {len(libres)} (eliminados: {antes - len(libres)})")

    if libres.empty:
        st.error("❌ No quedan conductores después de TODOS los filtros")
        return None, None, None, "S/P"

    st.write(f"✅ Conductores candidatos: **{len(libres)}**")
    
    # Buscar ubicaciones
    col_cond_u = next((c for c in df_u.columns if "CONDUCTOR" in c.upper()), None)
    col_lat_u = next((c for c in df_u.columns if "LAT" in c.upper()), None)
    col_lon_u = next((c for c in df_u.columns if "LON" in c.upper()), None)

    st.write(f"📍 Columnas encontradas en UBICACIONES:")
    st.write(f"  - Conductor: {col_cond_u}")
    st.write(f"  - Latitud: {col_lat_u}")
    st.write(f"  - Longitud: {col_lon_u}")

    if not (col_cond_u and col_lat_u and col_lon_u):
        st.error("❌ Faltan columnas en UBICACIONES")
        st.write("DATOS DE UBICACIONES:")
        st.dataframe(df_u)
        return None, None, None, "Error Ubi Cols"

    df_u['KEY_CLEAN'] = df_u[col_cond_u].astype(str).str.strip().str.upper()
    
    st.write("📍 Conductores en UBICACIONES:")
    st.write(df_u[['KEY_CLEAN', col_lat_u, col_lon_u]].to_string())

    mejor_chofer = None
    menor_distancia = float('inf')

    st.write("🔄 Buscando el más cercano...")
    
    for idx, chofer in libres.iterrows():
        n = str(chofer.get('NOMBRE', '')).replace('nan','').strip()
        a = str(chofer.get('APELLIDO', '')).replace('nan','').strip()
        nombre_completo = f"{n} {a}".strip().upper()
        
        st.write(f"🔎 Buscando: **{nombre_completo}**")

        ubi = df_u[df_u['KEY_CLEAN'] == nombre_completo]
        
        if not ubi.empty:
            try:
                lat_cond = float(ubi.iloc[-1][col_lat_u])
                lon_cond = float(ubi.iloc[-1][col_lon_u])
                
                st.write(f"  ✅ Ubicación: {lat_cond}, {lon_cond}")
                
                d = calcular_distancia_real(lat_cli, lon_cli, lat_cond, lon_cond)
                
                st.write(f"  📏 Distancia: **{d:.2f} km**")
                
                if d < 10000 and d < menor_distancia:
                    menor_distancia = d
                    mejor_chofer = chofer
                    st.success(f"  🎯 ¡MEJOR CANDIDATO hasta ahora!")
            except Exception as e:
                st.error(f"  ❌ Error: {e}")
                continue
        else:
            st.warning(f"  ⚠️ NO tiene ubicación GPS registrada")

    st.write("="*50)
    
    if mejor_chofer is not None:
        t = str(mejor_chofer.get('TELEFONO', '0000000000')).split('.')[0].strip()
        foto = str(mejor_chofer.get('FOTO_PERFIL', 'SIN_FOTO'))
        placa = str(mejor_chofer.get('PLACA', 'S/P'))
        n_final = f"{mejor_chofer.get('NOMBRE')} {mejor_chofer.get('APELLIDO')}"
        st.success(f"🎉 CONDUCTOR SELECCIONADO: {n_final} ({menor_distancia:.2f} km)")
        return mejor_chofer, t, foto, placa
    
    st.error("❌ NO SE ENCONTRÓ NINGÚN CONDUCTOR VÁLIDO")
    return None, None, None, "S/P"

# --- 📱 INTERFAZ ---
st.markdown('<div class="main-title">🚖 TAXI SEGURO</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">🌎 SERVICIO GLOBAL</div>', unsafe_allow_html=True)

# --- OBTENER UBICACIÓN GPS ---
loc = get_geolocation()
lat_actual, lon_actual = None, None

if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
    
    # Guardar en session_state para persistencia
    st.session_state.ultima_lat = lat_actual
    st.session_state.ultima_lon = lon_actual
    st.session_state.gps_ready = True
    
    st.markdown(f'<div class="gps-status">✅ GPS ACTIVO: {lat_actual:.5f}, {lon_actual:.5f}</div>', unsafe_allow_html=True)
else:
    # Usar última ubicación conocida si existe
    if st.session_state.ultima_lat and st.session_state.ultima_lon:
        lat_actual = st.session_state.ultima_lat
        lon_actual = st.session_state.ultima_lon
        st.info(f"📍 Usando última ubicación conocida: {lat_actual:.5f}, {lon_actual:.5f}")
    else:
        st.warning("⚠️ Esperando señal GPS... (Permite el acceso a tu ubicación)")

# --- PANTALLA DE SOLICITUD ---
if not st.session_state.viaje_confirmado:
    with st.form("form_pedido"):
        nombre_cli = st.text_input("👤 Tu Nombre:", key="nombre_input")
        celular_input = st.text_input("📱 WhatsApp (Sin código de país):", key="celular_input")
        ref_cli = st.text_input("📍 Referencia / Dirección:", key="ref_input")
        tipo_veh = st.selectbox("🚗 ¿Qué necesitas?", ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔"])
        
        enviar = st.form_submit_button("🚖 SOLICITAR UNIDAD", use_container_width=True)

    if enviar:
        # DEBUG: Mostrar estado del formulario
        st.info(f"🔍 DEBUG: Formulario enviado | GPS: {lat_actual is not None}")
        
        # Validaciones
        if not nombre_cli or not ref_cli:
            st.error("❌ Por favor completa todos los campos obligatorios")
        elif not celular_input or len(celular_input) < 7:
            st.error("❌ Ingresa un número de WhatsApp válido")
        elif not lat_actual or not lon_actual:
            st.error("🚫 Aún no tenemos tu ubicación GPS. Espera unos segundos y vuelve a intentar.")
        else:
            # PROCESAR SOLICITUD
            st.info("✅ Validaciones OK - Buscando conductor...")
            
            # ACTIVAR MODO DEBUG para detener auto-refresh
            st.session_state.debug_mode = True
            
            with st.spinner("🔍 Buscando conductor disponible..."):
                chof, t_chof, foto_chof, placa = obtener_chofer_mas_cercano(lat_actual, lon_actual, tipo_veh)
                
                # DEBUG: Mostrar resultado de búsqueda
                st.write(f"🔍 DEBUG - Chofer encontrado: {chof is not None}")
                
                if chof is not None:
                    # Limpieza de datos del conductor
                    n_clean = str(chof.get('NOMBRE', '')).replace('nan','').strip()
                    a_clean = str(chof.get('APELLIDO', '')).replace('nan','').strip()
                    nombre_chof = f"{n_clean} {a_clean}".strip().upper()
                    
                    st.write(f"✅ Conductor seleccionado: {nombre_chof}")
                    
                    id_v = f"TX-{random.randint(1000, 9999)}"
                    mapa_url = f"https://www.google.com/maps?q={lat_actual},{lon_actual}"
                    
                    # 1. Registrar Pedido
                    st.write("📝 Registrando pedido en Google Sheets...")
                    
                    datos_envio = {
                        "accion": "registrar_pedido",
                        "id_viaje": id_v,
                        "cliente": nombre_cli,
                        "tel_cliente": celular_input,
                        "referencia": ref_cli,
                        "conductor": nombre_chof,
                        "tel_conductor": t_chof,
                        "mapa": mapa_url
                    }
                    
                    st.write(f"📤 Datos a enviar: {datos_envio}")
                    
                    res_pedido = enviar_datos_a_sheets(datos_envio)
                    
                    st.write(f"📥 RESPUESTA DE SHEETS: `{res_pedido}`")
                    st.write(f"📏 Longitud respuesta: {len(str(res_pedido))} caracteres")
                    
                    # 2. SIMPLIFICAR VALIDACIÓN - Aceptar CUALQUIER respuesta que no sea error
                    es_error = (
                        "error" in str(res_pedido).lower() or
                        "failed" in str(res_pedido).lower() or
                        "falló" in str(res_pedido).lower()
                    )
                    
                    respuesta_ok = not es_error
                    
                    st.write(f"✔️ Respuesta válida: {respuesta_ok} (es_error: {es_error})")
                    
                    if respuesta_ok:
                        st.success("✅ PEDIDO REGISTRADO EXITOSAMENTE")
                        
                        # Cambiar estado del conductor
                        st.write("🔄 Cambiando estado del conductor...")
                        res_estado = enviar_datos_a_sheets({
                            "accion": "cambiar_estado", 
                            "conductor": nombre_chof, 
                            "estado": "OCUPADO"
                        })
                        st.write(f"Estado actualizado: {res_estado}")
                        
                        # Guardar datos del viaje
                        st.write("💾 Guardando datos en session_state...")
                        
                        st.session_state.datos_pedido = {
                            "chof": nombre_chof, 
                            "t_chof": t_chof, 
                            "foto": foto_chof, 
                            "placa": placa, 
                            "id": id_v, 
                            "mapa": mapa_url, 
                            "lat_cli": lat_actual, 
                            "lon_cli": lon_actual, 
                            "nombre": nombre_cli, 
                            "ref": ref_cli
                        }
                        
                        st.write("✅ Datos guardados. Activando viaje...")
                        st.session_state.viaje_confirmado = True
                        
                        st.write(f"🎯 Estado viaje_confirmado: {st.session_state.viaje_confirmado}")
                        
                        st.balloons()
                        st.success("🎉 ¡TODO LISTO! Recargando página...")
                        
                        # Esperar 2 segundos antes de recargar
                        import time
                        time.sleep(2)
                        
                        # Forzar recarga
                        st.rerun()
                    else:
                        st.error(f"❌ Error al registrar pedido")
                        st.error(f"Respuesta recibida: `{res_pedido}`")
                        st.warning("💡 Verifica que tu Google Apps Script esté funcionando correctamente")
                        
                        # MODO DE EMERGENCIA
                        st.divider()
                        st.info("🆘 **MODO DE EMERGENCIA ACTIVADO**")
                        st.write("Puedes continuar de todos modos para probar la interfaz:")
                        
                        if st.button("⚠️ CONTINUAR SIN REGISTRO (Solo prueba)", type="primary"):
                            st.session_state.datos_pedido = {
                                "chof": nombre_chof, 
                                "t_chof": t_chof, 
                                "foto": foto_chof, 
                                "placa": placa, 
                                "id": id_v, 
                                "mapa": mapa_url, 
                                "lat_cli": lat_actual, 
                                "lon_cli": lon_actual, 
                                "nombre": nombre_cli, 
                                "ref": ref_cli
                            }
                            st.session_state.viaje_confirmado = True
                            st.rerun()
                else:
                    st.warning("⚠️ No hay conductores disponibles")
                    st.info("Esto puede deberse a:")
                    st.write("- No hay conductores con estado LIBRE")
                    st.write("- No hay conductores del tipo solicitado")
                    st.write("- Todos los conductores están muy lejos")

# --- PANTALLA DE VIAJE ACTIVO ---
else:
    dp = st.session_state.datos_pedido
    
    # Encabezado con ID
    st.markdown(f'<div style="text-align:center;"><span class="id-badge">🆔 VIAJE: {dp["id"]}</span></div>', unsafe_allow_html=True)
    
    # Foto del conductor
    foto_data = dp.get('foto', "SIN_FOTO")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if foto_data and len(str(foto_data)) > 100:
            try:
                img_bytes = base64.b64decode(foto_data)
                st.image(io.BytesIO(img_bytes), width=150, caption=dp['chof'])
            except:
                st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=130)

    # Información del conductor
    st.success(f"✅ Conductor: **{dp['chof']}**")
    st.info(f"🚗 Vehículo: **{dp['placa']}**")
    
    # Botón de WhatsApp
    msg_wa = urllib.parse.quote(
        f"🚖 *HOLA TAXI SEGURO*\n"
        f"Soy {dp['nombre']}\n"
        f"🆔 ID Viaje: {dp['id']}\n"
        f"📍 Estoy en: {dp['ref']}\n"
        f"🗺️ Ver mapa: {dp['mapa']}"
    )
    
    st.markdown(
        f'<a href="https://api.whatsapp.com/send?phone={dp["t_chof"]}&text={msg_wa}" '
        f'target="_blank" style="background-color:#25D366;color:white;padding:15px;'
        f'text-align:center;display:block;text-decoration:none;font-weight:bold;'
        f'font-size:18px;border-radius:10px;margin:15px 0;">📲 CHATEAR CON CONDUCTOR</a>', 
        unsafe_allow_html=True
    )

    # Botón de cancelación
    col_a, col_b = st.columns([3, 2])
    with col_a:
        if st.button("❌ CANCELAR VIAJE", use_container_width=True):
            st.session_state.viaje_confirmado = False
            st.session_state.datos_pedido = {}
            st.rerun()
    with col_b:
        if st.button("🔄 NUEVO PEDIDO", use_container_width=True):
            st.session_state.viaje_confirmado = False
            st.session_state.datos_pedido = {}
            st.rerun()

    st.divider()

    # --- MAPA EN TIEMPO REAL ---
    try:
        df_u = cargar_datos("UBICACIONES")
        df_u.columns = df_u.columns.str.strip().str.upper()
        
        col_cond = next((c for c in df_u.columns if "CONDUCTOR" in c), None)
        col_lat = next((c for c in df_u.columns if "LAT" in c), None)
        col_lon = next((c for c in df_u.columns if "LON" in c), None)

        if col_cond and col_lat and col_lon:
            df_u['KEY_CLEAN'] = df_u[col_cond].astype(str).str.strip().str.upper()
            pos_t = df_u[df_u['KEY_CLEAN'] == str(dp['chof']).strip().upper()]
            
            if not pos_t.empty:
                lat_t = float(pos_t.iloc[-1][col_lat])
                lon_t = float(pos_t.iloc[-1][col_lon])
                
                dist_km = calcular_distancia_real(lat_t, lon_t, dp['lat_cli'], dp['lon_cli'])
                tiempo_min = max(1, round((dist_km / 30) * 60) + 2)
                
                txt_eta = f"⏱️ Llegada estimada: {tiempo_min} min" if tiempo_min > 1 else "🎯 ¡El conductor está llegando!"
                st.markdown(f'<div class="eta-box">{txt_eta}<br>📏 Distancia: {dist_km:.2f} km</div>', unsafe_allow_html=True)
                
                # Obtener ruta
                camino_data = obtener_ruta_carretera(dp['lon_cli'], dp['lat_cli'], lon_t, lat_t)
                
                # Puntos en el mapa
                puntos_mapa = pd.DataFrame([
                    {"lon": dp['lon_cli'], "lat": dp['lat_cli'], "color": [0, 255, 0, 200], "info": "👤 TÚ ESTÁS AQUÍ"},
                    {"lon": lon_t, "lat": lat_t, "color": [255, 0, 0, 200], "info": f"🚖 {dp['chof']}"}
                ])

                # Renderizar mapa
                st.pydeck_chart(pdk.Deck(
                    map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
                    initial_view_state=pdk.ViewState(
                        latitude=(lat_t + dp['lat_cli'])/2, 
                        longitude=(lon_t + dp['lon_cli'])/2, 
                        zoom=13.5, 
                        pitch=0
                    ),
                    tooltip={"text": "{info}"},
                    layers=[
                        pdk.Layer("PathLayer", data=camino_data, get_path="path", get_color=[0, 100, 255], get_width=6),
                        pdk.Layer("ScatterplotLayer", data=puntos_mapa, get_position="[lon, lat]", get_fill_color="color", get_radius=25, pickable=True)
                    ]
                ))
                
                # Botón de actualización manual
                if st.button("🔄 ACTUALIZAR UBICACIÓN", use_container_width=True):
                    st.rerun()
            else:
                st.warning("📡 Esperando señal GPS del conductor...")
        else:
            st.warning("⚠️ No se pudo cargar el mapa. Verifica la conexión.")
    except Exception as e:
        st.error(f"❌ Error al cargar mapa: {str(e)}")

# Footer
st.markdown('<div class="footer">📧 Soporte: soporte@taxiseguro.com<br>🌐 www.taxiseguro.com</div>', unsafe_allow_html=True)
