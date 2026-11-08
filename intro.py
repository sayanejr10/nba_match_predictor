"""Intro de l'app : un tir réaliste qui finit en « swish » dans le panier.

Tout est dessiné en SVG (dessin vectoriel) et animé en CSS, sans image externe ni JavaScript.
Les dessins sont transformés en images (data URI) : le navigateur les calcule une seule fois,
puis se contente de les déplacer, ce qui garde l'animation fluide, même sur téléphone.
"""
import math
from urllib.parse import quote

# Durée avant que le tableau de bord commence à apparaître (utilisée par app.py)
INTRO_OFFSET = "3.5s"


def _img(svg: str) -> str:
    """Transforme un SVG en adresse d'image utilisable dans <img src="...">."""
    return "data:image/svg+xml;utf8," + quote(svg)


# ----------------------------------------------------------------------------
# Le ballon
# ----------------------------------------------------------------------------
# 1. La surface qui tourne : cuir orange, grain en relief, coutures noires
BALL_SURFACE = _img("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <radialGradient id="g" cx="42%" cy="38%" r="72%">
      <stop offset="0" stop-color="#F7AE68"/><stop offset=".5" stop-color="#E8762C"/><stop offset="1" stop-color="#B9521A"/>
    </radialGradient>
    <filter id="grain" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="1.15" numOctaves="2" seed="7" result="n"/>
      <feDiffuseLighting in="n" surfaceScale="1.7" lighting-color="#ffffff" result="l">
        <feDistantLight azimuth="235" elevation="62"/>
      </feDiffuseLighting>
      <feComposite in="l" in2="SourceGraphic" operator="in" result="lc"/>
      <feBlend in="SourceGraphic" in2="lc" mode="multiply"/>
    </filter>
    <clipPath id="c"><circle cx="100" cy="100" r="96"/></clipPath>
  </defs>
  <g clip-path="url(#c)">
    <circle cx="100" cy="100" r="96" fill="url(#g)" filter="url(#grain)"/>
    <g fill="none" stroke="#1C0F07" stroke-width="5" stroke-linecap="round">
      <path d="M100 2 C124 60 124 140 100 198"/>
      <path d="M2 102 C60 84 140 84 198 102"/>
      <path d="M34 20 C74 66 74 134 34 180"/>
      <path d="M166 20 C126 66 126 134 166 180"/>
    </g>
    <g fill="none" stroke="#FFC48F" stroke-opacity=".22" stroke-width="1.2">
      <path d="M103 2 C127 60 127 140 103 198"/>
      <path d="M2 99 C60 81 140 81 198 99"/>
    </g>
  </g>
</svg>""")

# 2. L'éclairage, qui ne tourne pas : ombre de sphère, reflet de lumière, contour
BALL_LIGHT = _img("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <defs>
    <radialGradient id="s" cx="38%" cy="32%" r="78%">
      <stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset=".55" stop-color="#000" stop-opacity=".06"/>
      <stop offset=".84" stop-color="#000" stop-opacity=".38"/><stop offset="1" stop-color="#000" stop-opacity=".68"/>
    </radialGradient>
    <radialGradient id="h" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#fff" stop-opacity=".6"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="b" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#FF9A4A" stop-opacity=".35"/><stop offset="1" stop-color="#FF9A4A" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="100" cy="100" r="96" fill="url(#s)"/>
  <ellipse cx="148" cy="152" rx="34" ry="18" fill="url(#b)" transform="rotate(-40 148 152)"/>
  <ellipse cx="68" cy="56" rx="36" ry="24" fill="url(#h)" transform="rotate(-32 68 56)"/>
  <circle cx="100" cy="100" r="95" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="2"/>
</svg>""")


# ----------------------------------------------------------------------------
# Le panier (repère : le centre de l'arceau est en (0, 0))
# ----------------------------------------------------------------------------
BACKBOARD = _img("""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 190">
  <defs>
    <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#B9D4FF" stop-opacity=".20"/><stop offset=".5" stop-color="#B9D4FF" stop-opacity=".05"/>
      <stop offset="1" stop-color="#B9D4FF" stop-opacity=".16"/>
    </linearGradient>
    <linearGradient id="frame" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C7D0DC"/>
    </linearGradient>
    <clipPath id="in"><rect x="6" y="6" width="288" height="164" rx="3"/></clipPath>
  </defs>
  <rect x="3" y="3" width="294" height="170" rx="5" fill="url(#glass)" stroke="url(#frame)" stroke-width="6"/>
  <g clip-path="url(#in)" fill="#fff">
    <path d="M52 0 L108 0 L28 176 L-28 176Z" opacity=".07"/>
    <path d="M122 0 L138 0 L58 176 L42 176Z" opacity=".05"/>
    <path d="M250 0 L290 0 L230 176 L190 176Z" opacity=".04"/>
  </g>
  <rect x="100" y="88" width="100" height="74" fill="none" stroke="#fff" stroke-width="5"/>
  <rect x="0" y="174" width="300" height="16" rx="4" fill="#0E1729"/>
  <rect x="2" y="175" width="296" height="2" fill="#fff" opacity=".18"/>
</svg>""")

_RIM_DEFS = """
  <defs>
    <linearGradient id="r" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FF9140"/><stop offset=".5" stop-color="#E5560F"/><stop offset="1" stop-color="#9C3207"/>
    </linearGradient>
  </defs>"""

# Arrière de l'arceau (passe derrière le ballon) + la fixation sur la planche
RIM_BACK = _img(f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -36 144 60">{_RIM_DEFS}
  <path d="M-14 -34 H14 L10 -12 H-10Z" fill="#334155"/>
  <path d="M-14 -34 H14" stroke="#64748B" stroke-width="2"/>
  <path d="M-62 0 A62 13 0 0 1 62 0" fill="none" stroke="#B4430B" stroke-width="6"/>
</svg>""")

# Avant de l'arceau (passe devant le ballon), avec un reflet de lumière
RIM_FRONT = _img(f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-72 -36 144 60">{_RIM_DEFS}
  <path d="M-62 0 A62 13 0 0 0 62 0" fill="none" stroke="url(#r)" stroke-width="7" stroke-linecap="round"/>
  <path d="M-58 1.5 A58 10.5 0 0 0 20 12" fill="none" stroke="#FFD2A8" stroke-opacity=".7" stroke-width="1.6" stroke-linecap="round"/>
  <g fill="#9C3207">{"".join(f'<circle cx="{62 * math.cos(a):.1f}" cy="{13 * math.sin(a) + 2:.1f}" r="1.6"/>' for a in [i * math.pi / 6 for i in range(1, 6)])}</g>
</svg>""")


def _net(front: bool) -> str:
    """Filet en losanges. On sépare la moitié avant et la moitié arrière pour que le ballon passe entre les deux."""
    rings = [(0, 60, 12), (30, 50, 10), (60, 42, 8), (88, 36, 7)]   # (hauteur, demi-largeur, demi-profondeur)
    n = 12

    def point(i, k):
        y, rx, ry = rings[i]
        a = 2 * math.pi * k / n + i * math.pi / n
        return rx * math.cos(a), y + ry * math.sin(a), math.sin(a)

    segments = []
    for i in range(len(rings) - 1):
        for k in range(n):
            for k2 in (k, k - 1):
                x1, y1, z1 = point(i, k)
                x2, y2, z2 = point(i + 1, k2)
                if ((z1 + z2) / 2 > 0) == front:
                    segments.append(f"M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}")
    color, opacity, width = ("#F1F5F9", ".95", "1.7") if front else ("#94A3B8", ".55", "1.4")
    return _img(f"""
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-70 -16 140 116">
  <path d="{' '.join(segments)}" fill="none" stroke="{color}" stroke-opacity="{opacity}" stroke-width="{width}" stroke-linecap="round"/>
</svg>""")


NET_BACK = _net(front=False)
NET_FRONT = _net(front=True)


# ----------------------------------------------------------------------------
# Style et animations de l'intro
# ----------------------------------------------------------------------------
INTRO_CSS = """
<style>
:root { --o: 3.5s; }
.skip-cb { position: fixed; opacity: 0; pointer-events: none; }
.skip-cb:checked + .intro { display: none; }
:root:has(.skip-cb:checked) { --o: 0s !important; }

.intro { position: fixed; inset: 0; z-index: 100000; cursor: pointer; overflow: hidden; display: block;
         background: radial-gradient(120% 90% at 50% 28%, #24324F 0%, #0E1424 46%, #04060B 100%);
         animation: in-fade .35s ease-out both, in-out .55s ease-in 3.3s forwards; }
@keyframes in-fade { from { opacity: 0; } }
@keyframes in-out { to { opacity: 0; visibility: hidden; } }

/* Caméra : léger zoom avant pendant toute l'intro */
.scene { position: absolute; inset: 0; animation: push 3.8s cubic-bezier(.2, .6, .3, 1) both; }
@keyframes push { from { transform: scale(1.09); } }

/* Projecteurs */
.beam { position: absolute; top: -12%; width: 46vw; height: 125vh; filter: blur(10px); transform-origin: 50% 0;
        background: linear-gradient(to bottom, rgba(255,236,200,.22), rgba(255,236,200,0) 72%);
        clip-path: polygon(46% 0, 54% 0, 100% 100%, 0 100%); mix-blend-mode: screen; }
.beam.l { left: 4%;  transform: rotate(-24deg); animation: sway-l 5s ease-in-out infinite alternate; }
.beam.r { right: 4%; transform: rotate(24deg);  animation: sway-r 5s ease-in-out infinite alternate; }
@keyframes sway-l { to { transform: rotate(-17deg); } }
@keyframes sway-r { to { transform: rotate(17deg); } }

/* Foule floutée et flashs d'appareils photo */
.crowd { position: absolute; left: 0; right: 0; top: 50%; height: 24%; opacity: .55; filter: blur(1.2px);
         background:
           radial-gradient(circle, rgba(255,214,160,.55) 0 1.5px, transparent 2.6px) 0 0 / 22px 17px,
           radial-gradient(circle, rgba(140,180,255,.45) 0 1.2px, transparent 2.2px) 9px 6px / 31px 23px,
           radial-gradient(circle, rgba(255,255,255,.35) 0 1px, transparent 2px) 4px 12px / 17px 13px;
         -webkit-mask-image: linear-gradient(transparent, #000 30%, #000 70%, transparent);
                 mask-image: linear-gradient(transparent, #000 30%, #000 70%, transparent); }
.flashes { position: absolute; left: 0; right: 0; top: 52%; height: 20%;
           background:
             radial-gradient(circle, #fff 0 2px, transparent 6px) 12% 30% / 100% 100% no-repeat,
             radial-gradient(circle, #fff 0 2px, transparent 6px) 71% 60% / 100% 100% no-repeat,
             radial-gradient(circle, #fff 0 2px, transparent 6px) 38% 75% / 100% 100% no-repeat,
             radial-gradient(circle, #fff 0 2px, transparent 6px) 88% 25% / 100% 100% no-repeat;
           opacity: 0; animation: flash-pop 1.7s steps(1) .4s infinite; }
@keyframes flash-pop { 0% { opacity: 0; } 8% { opacity: .9; } 14% { opacity: 0; } 55% { opacity: .7; } 60% { opacity: 0; } }

/* Parquet en perspective, avec reflet sous le panier */
.floor { position: absolute; left: -30%; right: -30%; bottom: -4%; height: 52%; transform-origin: 50% 100%;
         transform: perspective(700px) rotateX(56deg);
         background:
           radial-gradient(40% 60% at 50% 0%, rgba(255,210,150,.28), transparent 70%),
           linear-gradient(to top, rgba(0,0,0,0) 30%, rgba(4,6,11,.92)),
           repeating-linear-gradient(90deg, #A86C31 0 46px, #B97C3E 46px 92px, #93602A 92px 138px, #B27437 138px 184px); }
.vignette { position: absolute; inset: 0; background: radial-gradient(75% 70% at 50% 42%, transparent 40%, rgba(0,0,0,.72) 100%); }

/* Panier : la planche, l'arceau et le filet sont empilés pour que le ballon passe DANS le panier */
.stage { position: absolute; left: 50%; top: 40%; width: 0; height: 0; }
.stage img { position: absolute; display: block; pointer-events: none; max-width: none !important; height: auto; }
.ball img { max-width: none !important; }
.board { left: -150px; top: -168px; width: 300px; height: 190px; z-index: 1;
         filter: drop-shadow(0 18px 30px rgba(0,0,0,.55)); }
.rim-back  { left: -72px; top: -36px; width: 144px; height: 60px; z-index: 2; }
.net-back  { left: -70px; top: -16px; width: 140px; height: 116px; z-index: 3; transform-origin: 50% 14%; }
.net-front { left: -70px; top: -16px; width: 140px; height: 116px; z-index: 5; transform-origin: 50% 14%;
             filter: drop-shadow(0 2px 2px rgba(0,0,0,.35)); }
.rim-front { left: -72px; top: -36px; width: 144px; height: 60px; z-index: 6;
             filter: drop-shadow(0 3px 3px rgba(0,0,0,.4)); }

/* Le ballon : chaque niveau gère un mouvement (horizontal, vertical, taille, chute, rotation) */
.shot { position: absolute; left: 0; top: 0; z-index: 4; }
.shot-y, .shot-z, .shot-drop { position: absolute; left: 0; top: 0; }
.ball { position: absolute; left: -37px; top: -40px; width: 74px; height: 74px; }
.ball img { position: absolute; inset: 0; width: 100%; height: 100%; }
.ball .surface { will-change: transform; }
.ball::after { content: ""; position: absolute; inset: 0; border-radius: 50%;
               box-shadow: 0 10px 22px rgba(0,0,0,.45); z-index: -1; }
.shot.ghost { opacity: .18; z-index: 3; }
.shot.ghost.g2 { opacity: .09; }

/* Trajectoire : X régulier, Y en parabole, et le ballon rapetisse en s'éloignant vers le panier */
.shot      { animation: shot-x 1.1s linear calc(.95s + var(--lag, 0s)) both; }
.shot-y    { animation: shot-y 1.1s calc(.95s + var(--lag, 0s)) both; }
.shot-z    { animation: shot-z 1.1s cubic-bezier(.3, .6, .5, 1) calc(.95s + var(--lag, 0s)) both; }
.shot-drop { animation: shot-drop .5s cubic-bezier(.45, 0, .9, .6) calc(2.05s + var(--lag, 0s)) forwards; }
.ball .surface { animation: backspin 1.6s linear calc(.95s + var(--lag, 0s)) both; }
@keyframes shot-x { from { transform: translateX(-24vw); } to { transform: translateX(0); } }
@keyframes shot-y {
  0%   { transform: translateY(44vh); animation-timing-function: cubic-bezier(.18, .7, .4, 1); }
  60%  { transform: translateY(-27vh); animation-timing-function: cubic-bezier(.6, 0, .82, .45); }
  100% { transform: translateY(0); } }
@keyframes shot-z { from { transform: scale(1.95); } to { transform: scale(1); } }
@keyframes shot-drop { to { transform: translateY(108px) scale(.94); opacity: 0; } }
@keyframes backspin { from { transform: rotate(0deg); } to { transform: rotate(-760deg); } }

/* Le filet s'étire quand le ballon le traverse (swish) */
.net-back, .net-front { animation: swish .75s cubic-bezier(.3, .7, .4, 1) 2.08s both; }
@keyframes swish {
  0%   { transform: none; }
  30%  { transform: scaleY(1.38) scaleX(.84); }
  55%  { transform: scaleY(.9) scaleX(1.05); }
  75%  { transform: scaleY(1.06) scaleX(.98); }
  100% { transform: none; } }
.burst { position: absolute; left: -160px; top: -100px; width: 320px; height: 220px; z-index: 7; pointer-events: none;
         background: radial-gradient(closest-side, rgba(255,240,215,.75), rgba(255,170,90,.25) 45%, transparent 75%);
         opacity: 0; mix-blend-mode: screen; animation: burst .7s ease-out 2.05s both; }
@keyframes burst { 0% { opacity: 0; transform: scale(.6); } 25% { opacity: 1; } 100% { opacity: 0; transform: scale(1.4); } }

/* Jauge de tir : se remplit, puis passe au vert au moment du lancer */
.meter { position: absolute; left: calc(50% - 24vw + 64px); top: calc(40% + 44vh - 88px); width: 14px; height: 96px;
         border-radius: 999px; background: rgba(8,12,22,.75); border: 2px solid rgba(255,255,255,.65); overflow: hidden;
         box-shadow: 0 6px 18px rgba(0,0,0,.5); animation: meter-out .3s ease-in 1.35s forwards; }
.meter i { position: absolute; left: 0; right: 0; bottom: 0; height: 100%; transform-origin: bottom;
           background: linear-gradient(to top, #F59E0B, #FACC15 60%, #A3E635);
           animation: meter-fill .6s cubic-bezier(.4, 0, .7, 1) .25s both, meter-green .25s ease-out .85s forwards; }
@keyframes meter-fill { from { transform: scaleY(0); } }
@keyframes meter-green { to { background: #22C55E; box-shadow: 0 0 18px #22C55E; } }
@keyframes meter-out { to { opacity: 0; transform: translateY(-10px); } }
.release { position: absolute; left: calc(50% - 24vw + 88px); top: calc(40% + 44vh - 70px); color: #4ADE80;
           font-family: 'Bungee', sans-serif; font-size: 15px; letter-spacing: 1.5px; text-transform: uppercase;
           text-shadow: 0 0 12px rgba(34,197,94,.7), 0 2px 4px rgba(0,0,0,.6); white-space: nowrap;
           opacity: 0; animation: release 1s ease-out .85s both; }
@keyframes release { 0% { opacity: 0; transform: translateY(6px) scale(.9); } 20% { opacity: 1; transform: none; }
                     70% { opacity: 1; } 100% { opacity: 0; transform: translateY(-14px); } }

/* Titre */
.intro-title { position: absolute; left: 0; right: 0; top: calc(40% + 150px); text-align: center; z-index: 8;
               font-family: 'Sedgwick Ave Display', cursive; font-size: 72px; color: #fff; letter-spacing: 2px; transform: rotate(-3deg); text-transform: uppercase;
               text-shadow: 0 0 24px rgba(96,165,250,.55), 0 4px 10px rgba(0,0,0,.6);
               animation: title-in .7s cubic-bezier(.34, 1.56, .64, 1) 2.3s both; }
.intro-title span { color: #60A5FA; }
@keyframes title-in { from { opacity: 0; transform: rotate(-3deg) translateY(14px) scale(.6); } }
.intro-skip .touch { display: none; }
.intro-skip { position: absolute; right: 24px; bottom: 20px; color: #94A3B8; font-size: 13px; z-index: 8;
              animation: in-fade .4s ease .5s both; }

@media (max-width: 680px) {
  .stage { transform: scale(.7); }
  .intro-title { font-size: 50px; top: calc(40% + 100px); }
  .meter { left: calc(50% - 24vw + 86px); top: calc(40% + 44vh - 120px); }
  .release { left: calc(50% - 24vw + 110px); top: calc(40% + 44vh - 100px); font-size: 12px; }
  .intro-skip .desk { display: none; }
  .intro-skip .touch { display: inline; }
}
@media (prefers-reduced-motion: reduce) { .intro { display: none !important; } }
</style>
"""


def _ball_layers(extra_class: str = "", lag: str = "0s") -> str:
    return (f'<div class="shot {extra_class}" style="--lag:{lag}"><div class="shot-y"><div class="shot-z"><div class="shot-drop">'
            f'<div class="ball"><img class="surface" src="{BALL_SURFACE}" alt=""><img src="{BALL_LIGHT}" alt=""></div>'
            f'</div></div></div></div>')


def intro_html() -> str:
    """Tout le HTML de l'intro, prêt à être affiché avec st.markdown(..., unsafe_allow_html=True)."""
    return INTRO_CSS + f"""
<input type="checkbox" id="skip-intro" class="skip-cb" aria-hidden="true" tabindex="-1">
<label for="skip-intro" class="intro" aria-hidden="true">
  <div class="scene">
    <div class="beam l"></div><div class="beam r"></div>
    <div class="crowd"></div><div class="flashes"></div>
    <div class="floor"></div>
    <div class="vignette"></div>
    <div class="stage">
      <img class="board" src="{BACKBOARD}" alt="">
      <img class="rim-back" src="{RIM_BACK}" alt="">
      <img class="net-back" src="{NET_BACK}" alt="">
      {_ball_layers("ghost g2", ".07s")}{_ball_layers("ghost", ".035s")}{_ball_layers()}
      <img class="net-front" src="{NET_FRONT}" alt="">
      <img class="rim-front" src="{RIM_FRONT}" alt="">
      <div class="burst"></div>
    </div>
    <div class="meter"><i></i></div>
    <div class="release">Perfect release</div>
    <div class="intro-title">Court<span>Side</span></div>
  </div>
  <div class="intro-skip"><span class="desk">Click to skip</span><span class="touch">Tap to skip</span></div>
</label>
"""