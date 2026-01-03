import streamlit as st
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import base64
import math
import os
import time
import io
from PIL import Image
from datetime import datetime
from streamlit_js_eval import get_geolocation
import requests
import streamlit.components.v1 as components

# --- 🔌 CONEXIÓN SEGURA A GOOGLE SHEETS ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
client = gspread.authorize(creds)

# --- ⚙️ CONFIGURACIÓN DE NEGOCIO ---
TARIFA_POR_KM = 0.05
DEUDA_MAXIMA = 10.00
LINK_PAYPAL = "https://paypal.me/CAMPOVERDEJARAMILLO"

# --- 🔗 CONFIGURACIÓN TÉCNICA ---
st.set_page_config(page_title="Portal Conductores", page_icon="🚖", layout="centered")
SHEET_ID = "1l3XXIoAggDd2K9PWnEw-7SDlONbtUvpYVw3UYD_9hus"
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbz-mcv2rnAiT10CUDxnnHA8sQ4XK0qLP7Hj2IhnzKp5xz5ugjP04HnQSN7OMvy4-4Al/exec"

# --- FUNCIÓN DE PAGO PAYPAL ---
def mostrar_boton_pago():
    st.header("🔓 Desbloqueo Automático (PayPal)")
    st.write("Paga tu suscripción y tu cuenta se activará al instante.")

    # 1. Pedimos la Cédula
    cedula_conductor = st.text_input("Ingresa tu número de Cédula para pagar:", max_chars=10)

    if cedula_conductor:
        client_id = "AS96Gq4_mueF7i7xjUzx2nEgYSmiS6t69datLVrPMwxDIxboQC00sZf7TBM6KwkRxUL92ys0I-JXXq_y"
        valor_a_pagar = "5.00"

        _html = f"""
        <div id="-button-container"></div>
        <script src="https://www..com/sdk/js?client-id={client_id}&currency=USD"></script>
        <script>
            .Buttons({{
                createOrder: function(data, actions) {{
                    return actions.order.create({{
                        purchase_units: [{{
                            amount: {{ value: '{valor_a_pagar}' }},
                            custom_id: '{cedula_conductor}'
                        }}]
                    }});
                }},
                onApprove: function(data, actions) {{
                    return actions.order.capture().then(function(details) {{
                        alert('¡Pago Exitoso! Tu cuenta {cedula_conductor} se está desbloqueando...');
                    }});
                }},
                onError: function (err) {{
                    console.error('Error:', err);
                    alert('Hubo un error con el pago. Intenta de nuevo.');
                }}
            }}).render('#-button-container');
        </script>
        """
        st.caption(f"Total a pagar: ${valor_a_pagar}")
        components.html(_html, height=180)
    else:
        st.info("👆 Escribe tu cédula para ver el botón de pago.")

def enviar_datos_requests(params):
    try:
        requests.post(URL_SCRIPT, params=params)
    except Exception as e:
        st.error(f"Error de conexión: {e}")

# --- 🔄 INICIALIZAR SESIÓN ---
if 'usuario_activo' not in st.session_state: st.session_state.usuario_activo = False
if 'datos_usuario' not in st.session_state: st.session_state.datos_usuario = {}

# --- 📋 LISTAS ---
PAISES = ["Ecuador", "Colombia", "Perú", "México", "España", "Otro"]
IDIOMAS = ["Español", "English"]
VEHICULOS = ["Taxi 🚖", "Camioneta 🛻", "Ejecutivo 🚔", "Moto Entrega 🏍️"]

# --- 🛰️ CAPTURA AUTOMÁTICA DE GPS ---
loc = get_geolocation()
if loc and 'coords' in loc:
    lat_actual = loc['coords']['latitude']
    lon_actual = loc['coords']['longitude']
else:
    lat_actual, lon_actual = None, None

# --- 🛠️ FUNCIONES ---
def cargar_datos(hoja):
    # --- IDs EXTRAÍDOS DE TUS IMÁGENES ---
    GID_CHOFERES = "773119638"
    GID_VIAJES   = "0"
    
    try:
        # Seleccionamos el ID correcto según la hoja que pida el código
        gid_actual = GID_CHOFERES if hoja == "CHOFERES" else GID_VIAJES
        
        # Usamos el enlace de exportación directa (Mucho más estable)
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid_actual}"
        
        # Leemos el archivo CSV
        df = pd.read_csv(url)
        
        # LIMPIEZA VITAL: Quitamos espacios invisibles en los títulos
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

def enviar_datos_a_sheets(datos):
    try:
        params = urllib.parse.urlencode(datos)
        with urllib.request.urlopen(f"{URL_SCRIPT}?{params}") as response:
            return response.read().decode('utf-8')
    except: return "Error"

# --- 📱 INTERFAZ ---
st.title("🚖 Portal de Socios")

if st.session_state.usuario_activo:
    # --- PANEL DEL CONDUCTOR LOGUEADO ---
    df_fresh = cargar_datos("CHOFERES")
    user_nom = str(st.session_state.datos_usuario['Nombre']).strip()
    user_ape = str(st.session_state.datos_usuario['Apellido']).strip()
    
    # Creamos el nombre completo EXACTO para sincronizar con la hoja UBICACIONES
    nombre_completo_unificado = f"{user_nom} {user_ape}".upper()
    
    # BUSCAMOS LA FILA DEL USUARIO EN EL EXCEL
    fila_actual = df_fresh[
        (df_fresh['Nombre'].astype(str).str.upper().str.strip() == user_nom.upper()) & 
        (df_fresh['Apellido'].astype(str).str.upper().str.strip() == user_ape.upper())
    ]
    
    # --- LÓGICA DE ACTUALIZACIÓN DE UBICACIÓN ---
    st.subheader(f"Bienvenido, {nombre_completo_unificado}")

    # --- 📸 SECCIÓN DE FOTO DE PERFIL ---
    # Buscamos la foto: primero en la sesión (por si acaba de cambiar) y luego en el Excel
    foto_actual = st.session_state.datos_usuario.get('Foto_Perfil', 'SIN_FOTO')
    if foto_actual == "SIN_FOTO" and not fila_actual.empty:
        try:
            foto_actual = fila_actual.iloc[0]['Foto_Perfil']
        except: pass

    col_img, col_btn = st.columns([1, 2])

    with col_img:
        if foto_actual and str(foto_actual) != "nan" and len(str(foto_actual)) > 100:
            try:
                img_bytes = base64.b64decode(foto_actual)
                st.image(io.BytesIO(img_bytes), width=150)
            except:
                st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/149/149071.png", width=120)

    with col_btn:
        st.write("📷 **¿Deseas cambiar tu foto?**")
        archivo_nuevo = st.file_uploader("Sube una imagen (150x150)", type=["jpg", "png", "jpeg"], key="panel_ch_foto")
        
        if archivo_nuevo:
            if st.button("💾 GUARDAR NUEVA FOTO"):
                with st.spinner("Optimizando..."):
                    img = Image.open(archivo_nuevo).convert("RGB")
                    img = img.resize((150, 150)) 
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG", quality=60) 
                    foto_b64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    res = enviar_datos({
                        "accion": "actualizar_foto_perfil",
                        "email": fila_actual.iloc[0]['Email'],
                        "foto": foto_b64
                    })
                    
                    if res:
                        st.success("✅ ¡Foto guardada!")
                        # Actualizamos la foto en la memoria de la App de inmediato
                        st.session_state.datos_usuario['Foto_Perfil'] = foto_b64
                        time.sleep(1) 
                        st.rerun()
    st.write("---") # Separador visual antes del GPS
    # Añadimos 'value=True' para que intente conectar apenas entre
    if st.checkbox("🛰️ ACTIVAR RASTREO GPS", value=True):
        # Usamos las variables lat_actual y lon_actual que definiste en la línea 29
        if lat_actual and lon_actual:
            res = enviar_datos({
                "accion": "actualizar_ubicacion",
                "conductor": nombre_completo_unificado,
                "latitud": lat_actual,
                "longitud": lon_actual
            })
            if res:
                st.success(f"📍 Ubicación activa: {lat_actual}, {lon_actual}")
        else:
            # Esto se quita cuando das clic en 'Hecho' en el navegador
            st.warning("🛰️ Esperando señal de GPS... Por favor, permite el acceso en tu navegador.")
    
    # --- MOSTRAR INFORMACIÓN DEL SOCIO ---
    if not fila_actual.empty:
        # Columna R (Índice 17) es DEUDA
        deuda_actual = float(fila_actual.iloc[0, 17])
        # Columna I (Índice 8) es Estado
        estado_actual = str(fila_actual.iloc[0, 8]) 
        
        # Bloqueo Automático (Sin rerun inmediato para permitir ver pagos)
        if deuda_actual >= DEUDA_MAXIMA and "LIBRE" in estado_actual.upper():
            st.error("⚠️ DESCONEXIÓN AUTOMÁTICA: Tu deuda superó el límite permitido.")
            enviar_datos({
                "accion": "actualizar_estado", 
                "nombre": user_nom, 
                "apellido": user_ape, 
                "estado": "OCUPADO"
            })
            # No hacemos st.rerun() aquí para que cargue la interfaz de abajo

        # --- BOTÓN DE PAGO (Visible siempre que haya deuda alta) ---
        if deuda_actual >= DEUDA_MAXIMA:
            st.error(f"⚠️ TU CUENTA ESTÁ BLOQUEADA. Debes: ${deuda_actual}")
            mostrar_boton_pago()
        
        # ---------------------------------------------------
        # 💰 SECCIÓN DE PAGOS UNIFICADA (Aquí está lo nuevo)
        # ---------------------------------------------------
        
        # 1. INDICADORES VISUALES
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("💸 Deuda Actual", f"${deuda_actual:.2f}")
        col_m2.metric("🚦 Estado Actual", estado_actual)

        # 2. SECCIÓN DE PAGOS (Solo aparece si debe dinero y no está bloqueado crítico o si quiere adelantar)
        if deuda_actual > 0:
            st.markdown("---")
            st.subheader("💳 Centro de Pagos")
            st.warning(f"Saldo pendiente: **${deuda_actual:.2f}**")
            
            # Pestañas de Pago
            tab_deuna, tab_ = st.tabs(["📲 Pagar con DEUNA", "🌎 Pagar con PAYPAL"])
            
            with tab_deuna:
                st.write("**Escanea el QR:**")
                try:
                    # Asegúrate de que 'qr_deuna.png' exista en tu GitHub
                    st.image("qr_deuna.png", caption="QR Banco Pichincha", width=250)
                except:
                    st.error("⚠️ No se encontró 'qr_deuna.png' en GitHub")
                
                # --- BOTÓN DE WHATSAPP INTEGRADO ---
                msg_wa = f"Hola, soy {nombre_completo_unificado}. Adjunto mi comprobante de pago DEUNA para actualizar mi saldo."
                msg_encoded = urllib.parse.quote(msg_wa)
                # Tu número de WhatsApp (593 es el código de Ecuador)
                numero_whatsapp = "593960643638" 
                
                st.markdown(f'''
                    <a href="https://wa.me/{numero_whatsapp}?text={msg_encoded}" target="_blank" style="text-decoration:none;">
                        <div style="background-color:#25D366;color:white;padding:12px;text-align:center;border-radius:10px;font-weight:bold;margin-top:10px;">
                            📲 ENVIAR COMPROBANTE AL WHATSAPP
                        </div>
                    </a>
                ''', unsafe_allow_html=True)
            tab_qr, tab_paypal = st.tabs(["📲 Transferencia/QR", "💳 Tarjeta / PayPal"])
            with tab_paypal:
                st.subheader("🌎 Pagar con PayPal")
                
                # --- 1. CONFIGURACIÓN DEL MONTO ---
                # Si debe dinero, sugerimos el total. Si no, $5.00
                sugerencia = float(deuda_actual) if deuda_actual > 0 else 5.00
                
                st.write("Confirma o escribe la cantidad a pagar:")
                
                # CASILLA: El conductor puede borrar y poner $1, $5, $10, etc.
                monto_final = st.number_input("Monto a Pagar ($):", min_value=1.00, value=sugerencia, step=1.00)
                
                # Datos para PayPal
                cedula_usuario = str(fila_actual.iloc[0, 0]) 
                client_id = "AbTSfP381kOrNXmRJO8SR7IvjtjLx0Qmj1TyERiV5RzVheYAAxvgGWHJam3KE_iyfcrf56VV_k-MPYmv"

                # --- 2. EL BOTÓN OFICIAL (SMART BUTTON) ---
                paypal_html_tab = f"""
                <div id="paypal-button-container-tab"></div>
                <script src="https://www.paypal.com/sdk/js?client-id={client_id}&currency=USD"></script>
                <script>
                    paypal.Buttons({{
                        createOrder: function(data, actions) {{
                            return actions.order.create({{
                                purchase_units: [{{
                                    amount: {{ value: '{monto_final}' }},
                                    custom_id: '{cedula_usuario}' 
                                }}]
                            }});
                        }},
                        onApprove: function(data, actions) {{
                            return actions.order.capture().then(function(details) {{
                                alert('✅ Pago de ${monto_final} exitoso. Tu cuenta se actualizará en breve.');
                            }});
                        }},
                        onError: function (err) {{
                            console.error('Error:', err);
                            alert('❌ No se pudo procesar el pago.');
                        }}
                    }}).render('#paypal-button-container-tab');
                </script>
                """
                components.html(paypal_html_tab, height=180)
                
                # --- 3. AVISOS DE BLOQUEO (TOPE $10) ---
                if deuda_actual >= DEUDA_MAXIMA:
                    # Calculamos cuánto le falta pagar para desbloquearse
                    minimo_para_desbloqueo = deuda_actual - DEUDA_MAXIMA + 0.01
                    st.error(f"⚠️ CUENTA BLOQUEADA (Deuda: ${deuda_actual}).")
                    st.info(f"💡 Para desbloquearte, debes pagar al menos: **${minimo_para_desbloqueo:.2f}**")
                elif deuda_actual > 0:
                    st.warning(f"Tienes deuda pendiente, pero aún puedes trabajar (Límite: ${DEUDA_MAXIMA}).")
                else:
                    st.success("✅ Estás al día. Puedes recargar saldo a favor.")
        
        st.divider()
        # ---------------------------------------------------

        # ==========================================
        # 🚀 BLOQUE INTELIGENTE: GESTIÓN DE VIAJE
        # ==========================================
        st.subheader("Gestión de Viaje")
        
        # 1. Consultamos la hoja VIAJES
        df_viajes = cargar_datos("VIAJES")
        viaje_activo = pd.DataFrame() 

        # 2. Filtramos: ¿Existe un viaje "EN CURSO" para este conductor?
        if not df_viajes.empty and 'Conductor' in df_viajes.columns:
            viaje_activo = df_viajes[
                (df_viajes['Conductor'].astype(str).str.upper() == nombre_completo_unificado) & 
                (df_viajes['Estado'].astype(str) == "EN CURSO")
            ]

        # 3. DECISIÓN DEL SISTEMA
        if not viaje_activo.empty and "OCUPADO" in estado_actual:
            
            # CASO A: HAY PASAJERO -> Mostramos datos y el botón de Finalizar
            datos_v = viaje_activo.iloc[-1]
            st.warning("🚖 TIENES UN PASAJERO A BORDO")
            
            st.write(f"👤 **Cliente:** {datos_v.get('Cliente', 'S/D')}")
            st.write(f"📞 **Tel:** {datos_v.get('Tel Cliente', 'S/D')}")
            st.write(f"📍 **Destino:** {datos_v.get('Referencia', 'S/D')}")
            st.markdown(f"[🗺️ Ver Mapa]({datos_v.get('Mapa', '#')})")

            if st.button("🏁 FINALIZAR VIAJE Y COBRAR", type="primary", use_container_width=True):
                with st.spinner("Calculando distancia y actualizando deuda..."):
                    try:
                        # 1. Obtenemos coordenadas desde el link del mapa
                        link_mapa = str(datos_v.get('Mapa', ''))
                        distancia = 2.0 # Valor por defecto

                        # Intentamos parsear el link del mapa si tiene el formato esperado
                        if '0' in link_mapa and ',' in link_mapa:
                            try:
                                lat_cli = float(link_mapa.split('0')[1].split(',')[0])
                                lon_cli = float(link_mapa.split('0')[1].split(',')[1])
                                
                                # Fórmula Haversine para distancia real
                                dLat = math.radians(lat_actual - lat_cli)
                                dLon = math.radians(lon_actual - lon_cli)
                                a = math.sin(dLat/2)**2 + math.cos(math.radians(lat_cli)) * \
                                    math.cos(math.radians(lat_actual)) * math.sin(dLon/2)**2
                                c = 2 * math.asin(math.sqrt(a))
                                distancia = 6371 * c # KM en linea recta
                            except:
                                pass # Si falla el cálculo GPS, usamos el defecto
                        
                        # Ajuste de seguridad: Mínimo 1 km
                        if distancia < 1.0: distancia = 1.0
                        
                        # 2. Cálculo de Comisión
                        comision_nueva = round(distancia * TARIFA_POR_KM, 2)
                        
                        # 3. ENVIAR AL SCRIPT
                        res = enviar_datos_a_sheets({
                            "accion": "finalizar_y_deuda",
                            "conductor": nombre_completo_unificado,
                            "comision": comision_nueva,
                            "km": round(distancia, 2)
                        })
                        
                        if res == "Ok":
                            st.success(f"✅ Viaje Finalizado. Comisión de ${comision_nueva} cargada.")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Error de conexión con el servidor.")
                    except Exception as e:
                        st.error(f"❌ Error técnico: {e}") 

        else:
            # CASO B: NO HAY PASAJERO -> Verificamos deuda antes de permitir trabajar
            if deuda_actual >= 10.00:
                st.error(f"🚫 CUENTA BLOQUEADA: Tu deuda (${deuda_actual:.2f}) supera el límite de $10.00")
                st.info("Para volver a recibir viajes, por favor cancela tu saldo pendiente usando la sección de pagos arriba.")
                
                # Botón deshabilitado para evitar que el chofer se ponga LIBRE
                st.button("🟢 PONERME LIBRE", disabled=True, help="Debes pagar tu deuda para activar este botón")
            else:
                # Si la deuda es menor a $10, permitimos cambiar estado normalmente
                if "OCUPADO" in estado_actual:
                    st.info("Estás en estado OCUPADO (Sin pasajero de App).")

                col_lib, col_ocu = st.columns(2)
                with col_lib:
                    if st.button("🟢 PONERME LIBRE", use_container_width=True):
                        enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "LIBRE"})
                        st.rerun()
                with col_ocu:
                    if st.button("🔴 PONERME OCUPADO", use_container_width=True):
                        enviar_datos({"accion": "actualizar_estado", "nombre": user_nom, "apellido": user_ape, "estado": "OCUPADO"})
                        st.rerun()
        
    with st.expander("📜 Ver Mi Historial de Viajes"):
        if 'df_viajes' not in locals():
            df_viajes = cargar_datos("VIAJES")
            
        if not df_viajes.empty and 'Conductor Asignado' in df_viajes.columns:
            # Filtramos los viajes de este conductor específico
            mis_viajes = df_viajes[df_viajes['Conductor Asignado'].astype(str).str.upper() == nombre_completo_unificado]
            
            if not mis_viajes.empty:
                cols_mostrar = ['Fecha', 'Nombre del cliente', 'Referencia', 'Estado']
                cols_finales = [c for c in cols_mostrar if c in mis_viajes.columns]
                st.dataframe(mis_viajes[cols_finales].sort_values(by='Fecha', ascending=False), use_container_width=True)
            else:
                st.info("Aún no tienes historial de viajes.")
        else:
            st.write("Cargando datos...")     
    
    if st.button("🔒 CERRAR SESIÓN"):
        st.session_state.usuario_activo = False
        st.rerun()
    st.stop()
else:
    # --- PANTALLA INICIAL: LOGIN Y REGISTRO ---
    tab_log, tab_reg = st.tabs(["🔐 INGRESAR", "📝 REGISTRARME"])
    
    with tab_log:
        st.subheader("Acceso Socios")
        l_nom = st.text_input("Nombre registrado")
        l_ape = st.text_input("Apellido registrado")
        l_pass = st.text_input("Contraseña", type="password")
        
        if st.button("ENTRAR AL PANEL", type="primary"):
            df = cargar_datos("CHOFERES")
            # Validación por Nombre, Apellido y Clave
            match = df[(df['Nombre'].astype(str).str.upper() == l_nom.upper()) & 
                       (df['Apellido'].astype(str).str.upper() == l_ape.upper()) & 
                       (df['Clave'].astype(str) == l_pass)]
            
            if not match.empty:
                st.session_state.usuario_activo = True
                st.session_state.datos_usuario = match.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("❌ Datos incorrectos o usuario no encontrado.")
    st.markdown("---") 
    with st.expander("¿Olvidaste tu contraseña?"):
        st.info("Ingresa tu correo registrado para recibir tu clave:")
        email_recup = st.text_input("Tu Email", key="email_recup")
        
        if st.button("📧 Recuperar Clave"):
            if "@" in email_recup:
                with st.spinner("Conectando con el sistema..."):
                    try:
                        # Petición al Script de Google
                        resp = requests.post(URL_SCRIPT, params={
                            "accion": "recuperar_clave",
                            "email": email_recup
                        })
                        
                        if "CORREO_ENVIADO" in resp.text:
                            st.success("✅ ¡Enviado! Revisa tu correo (Bandeja de entrada o Spam).")
                        elif "EMAIL_NO_ENCONTRADO" in resp.text:
                            st.error("❌ Ese correo no está registrado como socio.")
                        else:
                            st.error("Error de conexión.")
                    except:
                        st.error("Error al conectar con el servidor.")
            else:
                st.warning("Escribe un correo válido.")
    with tab_reg:
        with st.form("registro_form"):
            st.subheader("Registro de Nuevos Socios")
            col1, col2 = st.columns(2)
            with col1:
                r_nom = st.text_input("Nombres *")
                r_ced = st.text_input("Cédula/ID *")
                r_email = st.text_input("Email *")
                r_pais = st.selectbox("País *", PAISES)
            with col2:
                r_ape = st.text_input("Apellidos *")
                r_telf = st.text_input("WhatsApp (Sin código) *")
                r_veh = st.selectbox("Tipo de Vehículo *", VEHICULOS)
                r_idioma = st.selectbox("Idioma", IDIOMAS)
    
            r_dir = st.text_input("Dirección *")
            r_pla = st.text_input("Placa *")
            r_pass1 = st.text_input("Contraseña *", type="password")
            
            # --- 📸 1. NUEVO: CAMPO PARA SUBIR FOTO ---
            st.write("---")
            st.write("📷 **Foto de Perfil** (Opcional)")
            archivo_foto_reg = st.file_uploader("Sube tu foto", type=["jpg", "png", "jpeg"])
            # ------------------------------------------
            
            if st.form_submit_button("✅ COMPLETAR REGISTRO"):
                if r_nom and r_email and r_pass1:
                    
                    # --- ⚙️ PROCESAR FOTO ---
                    foto_para_guardar = "SIN_FOTO"
                    if archivo_foto_reg is not None:
                        try:
                            img = Image.open(archivo_foto_reg).convert('RGB') # Aseguramos formato
                            img = img.resize((150, 150))
                            buffered = io.BytesIO()
                            img.save(buffered, format="JPEG", quality=70)
                            foto_para_guardar = base64.b64encode(buffered.getvalue()).decode()
                        except Exception as e:
                            st.error(f"Error procesando imagen: {e}")

                    # --- 💾 GUARDAR DIRECTAMENTE EN EXCEL (MÉTODO SEGURO) ---
                    try:
                        with st.spinner("Registrando conductor..."):
                            # 1. Abrir hoja. IMPORTANTE: Asegúrate que tu pestaña se llame "Sheet1"
                            sh = client.open("BD_TAXI_PRUEBAS")
                            try:
                                wks = sh.worksheet("Sheet1")
                            except:
                                wks = sh.worksheet("Hoja 1") # Intento alternativo

                            # 2. Preparar los datos en ORDEN DE COLUMNAS
                            # (Fecha, Nombre, Apellido, Cedula, Email, Direccion, Telefono, Placa, Estado, Vence, Clave, Foto, Validado)
                            nueva_fila = [
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Fecha
                                r_nom,
                                r_ape,
                                r_ced,
                                r_email,
                                r_dir,
                                r_telf,
                                r_pla,
                                "LIBRE",        # Estado inicial
                                "",             # Vence_Suscripcion (Vacio)
                                r_pass1,
                                foto_para_guardar,
                                "NO"            # Validado
                            ]

                            # 3. Escribir fila
                            wks.append_row(nueva_fila)
                            
                            st.success("✅ ¡Registro Exitoso! Ya puedes ingresar desde la pestaña superior.")
                            st.balloons()
                            
                    except Exception as e:
                        st.error(f"❌ Error al guardar en Excel: {e}")
                else:
                    st.warning("Por favor, completa los campos obligatorios (*)")
    
                    # --- 📤 3. AGREGAMOS LA FOTO AL ENVÍO ---
                    res = enviar_datos({
                        "accion": "registrar_conductor", 
                        "nombre": r_nom, 
                        "apellido": r_ape, 
                        "cedula": r_ced, 
                        "email": r_email, 
                        "direccion": r_dir, 
                        "telefono": r_telf, 
                        "placa": r_pla, 
                        "clave": r_pass1, 
                        "foto": foto_para_guardar,  # <--- AQUÍ VA LA FOTO NUEVA
                        "pais": r_pais, 
                        "idioma": r_idioma, 
                        "Tipo_Vehiculo": r_veh
                    })
                    
                    # Mensaje de éxito o error según responda tu función
                    if res: 
                        st.success("¡Registro exitoso! Ya puedes ingresar desde la pestaña superior.")
                else:
                    st.warning("Por favor, completa los campos obligatorios (*)")

st.markdown('<div style="text-align:center; color:#888; font-size:12px; margin-top:50px;">© 2025 Taxi Seguro Global</div>', unsafe_allow_html=True)

# El Radar: Solo se activa si hay un usuario logueado y está LIBRE
if st.session_state.get('usuario_activo', False):
    # Buscamos el estado dentro de los datos guardados en sesión
    datos = st.session_state.get('datos_usuario', {})
    estado_chofer = datos.get('estado', 'OCUPADO') # Por seguridad asumimos ocupado si falla
    
    # Si está LIBRE, activamos el conteo regresivo
    if "LIBRE" in str(estado_chofer):
        time.sleep(15)  # Espera 15 segundos
        st.rerun()      # Recarga la página para buscar viajes nuevos
