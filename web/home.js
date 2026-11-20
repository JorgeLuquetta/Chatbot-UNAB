// Botón "Inicio" (icono de casa) que vuelve al portal con todas las herramientas.
// Con dominio: https://portal.traumado.top/ · con IP: http://<ip>:9003/ · en el propio portal: "/".
(function () {
  var h = location.hostname;
  var onPortal = h.indexOf("portal.") === 0 || location.port === "9003";
  var url = onPortal ? "/" : (/traumado\.top$/.test(h) ? "https://portal.traumado.top/" : location.protocol + "//" + h + ":9003/");
  if (onPortal && (location.pathname === "/" || location.pathname === "/index.html")) return; // ya estás en el inicio
  var a = document.createElement("a");
  a.href = url;
  a.className = "home-btn";
  a.title = "Volver al inicio";
  a.setAttribute("aria-label", "Volver al inicio");
  a.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" ' +
    'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/>' +
    '<path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/></svg>';
  var css = document.createElement("style");
  css.textContent =
    ".home-btn{position:fixed;top:14px;left:14px;z-index:1000;width:44px;height:44px;border-radius:50%;" +
    "display:flex;align-items:center;justify-content:center;color:#6a4fd6;background:rgba(255,255,255,.85);" +
    "border:1px solid rgba(106,79,214,.25);box-shadow:0 6px 20px -8px rgba(110,80,200,.45);text-decoration:none;" +
    "backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);transition:transform .15s}" +
    ".home-btn:hover{transform:scale(1.06)}.home-btn:focus-visible{outline:3px solid #6a4fd6;outline-offset:2px}" +
    "@media (prefers-color-scheme:dark){.home-btn{background:rgba(34,28,58,.85);color:#c9b8ff;border-color:rgba(201,184,255,.25)}}" +
    "@media (max-width:560px){.home-btn{top:10px;left:10px;width:40px;height:40px}}";
  document.head.appendChild(css);
  (document.body || document.documentElement).appendChild(a);
})();
