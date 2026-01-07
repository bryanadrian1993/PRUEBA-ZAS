import streamlit as st
from PIL import Image

# Configuración de la página
st.set_page_config(
    page_title="Sobre el fundador y ZAS",
    page_icon="🌐",
    layout="centered"
)

# Estilos para darle un toque profesional
st.markdown("""
<style>
    .founder-name { font-size: 1.8rem; color: #1E3A8A; font-weight: bold; }
    .justified-text { text-align: justify; }
</style>
""", unsafe_allow_html=True)

# --- SECCIÓN 1: BIOGRAFÍA DEL FUNDADOR ---
st.title("BIOGRAFIA DEL FUNDADOR")
st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    try:
        # La foto debe llamarse 'foto_perfil.jpg'
        image = Image.open("foto_perfil.jpg")
        st.image(image, caption="Adrian Campoverde Jaramillo", use_column_width=True)
    except:
        st.info("📷 (Espacio para foto)")
        st.caption("Sube 'foto_perfil.jpg'")

with col2:
    st.markdown('<div class="founder-name">ADRIAN CAMPOVERDE JARAMILLO</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="justified-text">
    Con una sólida formación en <b>Gerencia de Proyectos</b> y certificación <b>Lean Six Sigma Black Belt</b>, Adrián Campoverde se especializa en transformar procesos complejos en soluciones eficientes. Su experiencia abarca el liderazgo de equipos multidisciplinarios y la gestión estratégica en diversos sectores industriales y gubernamentales.
    <br><br>
    Actualmente, Adrián fusiona su experticia técnica con una visión humanista y global, respaldada por su formación en <b>Relaciones Internacionales y Turismo</b>. Como fundador de <b>ZasTaxi</b>, aplica estos estándares de calidad y gestión para desarrollar tecnología que no solo innova, sino que aporta soluciones reales y sostenibles a sus usuarios.
    </div>
    """, unsafe_allow_html=True)

# --- SECCIÓN 2: VISIÓN ZASTAXI ---
st.markdown("---")
st.header("🌐 ¿Qué es ZasTaxi? (Visión Global)")
st.write("""
ZasTaxi es una plataforma tecnológica de movilidad global diseñada para transformar el transporte en cualquier ciudad del mundo. Su arquitectura digital es universal: conecta a conductores y pasajeros en tiempo real, sin importar las fronteras, ofreciendo una solución de transporte segura, eficiente y escalable.
""")

# --- SECCIÓN 3: UTILIDAD ---
st.header("🎯 ¿Para qué sirve?")
st.write("ZasTaxi es un ecosistema digital que resuelve problemas universales de movilidad:")

st.info("""
**1. Conectividad Sin Fronteras 🌎**
Funciona como un enlace global. Un usuario puede usar la misma App para pedir un taxi en Ecuador, en México o en Europa, encontrando siempre el mismo estándar de seguridad y confianza.
""")

st.info("""
**2. Tecnología Adaptable a Cualquier Mercado 🏙️**
Nuestra tecnología se adapta a las necesidades locales de cada ciudad (tráfico, turismo, seguridad), permitiendo que comunidades de todo el mundo modernicen su transporte sin perder su identidad.
""")

st.info("""
**3. Integración Turística Internacional ✈️**
ZasTaxi es el compañero de viaje ideal. No solo te mueve de un punto A a un punto B, sino que te guía hacia las experiencias locales más auténticas, dinamizando economías en cualquier latitud.
""")

# Pie de página simple
st.markdown("---")
st.caption("© 2026 ZasTaxi Global - Todos los derechos reservados.")
