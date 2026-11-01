// UI strings. The language follows the browser (Spanish or English) unless picked by hand.
const STRINGS = {
  en: {
    tagline: 'Your PC audio on every speaker in the house, in sync.',
    theme: 'Theme', themeAuto: 'Auto', themeLight: 'Light', themeDark: 'Dark',
    language: 'Language', langAuto: 'Auto',
    allOn: '⏻ Everything on', allOff: '⏻ Everything off',
    masterVolume: 'Master volume',
    testBeep: '🔔 Test beep', testBeepTitle: 'A short beep every second for 20 s to align speakers by ear',
    autoSync: '⚖ Auto-sync', autoSyncTitle: 'Measures how late every speaker is and aligns them to the slowest one',
    search: '🔍 Find speakers',
    mode: 'Mode:',
    modeSync: '🎯 Synced', modeSyncTitle: 'All Windows audio goes through HouseBeat, so this PC can be delayed too',
    modeDirect: '⚡ Direct', modeDirectTitle: 'This PC plays live; only the other speakers are delayed',
    quit: '⏻ Quit', quitTitle: 'Puts the sound back on your main output and closes HouseBeat',
    offBanner: 'HouseBeat is off: your PC sounds as usual. Turn everything on to start playing on your speakers.',
    noVirtual: 'No virtual audio device found, so synced mode is not available. Install the free <a href="https://vb-audio.com/Cable/" target="_blank" rel="noopener">VB-CABLE</a> driver and restart HouseBeat.',
    volume: 'Volume', added: 'Added', addedTitle: 'Extra delay HouseBeat adds to wait for the slowest speaker',
    trim: 'Trim', trimTitle: 'What this speaker adds after what HouseBeat can measure (TV, Bluetooth, distance). If it sounds late, raise it; if it sounds early, lower it. Everything re-syncs by itself.',
    soundsLate: 'sounds late', soundsEarly: 'sounds early',
    format: 'Format', formatTitle: 'WAV is heavier, but some devices start sooner with it',
    mp3: 'MP3 (light)', wav: 'WAV (uncompressed)',
    reconnect: '↻ Reconnect', makeMain: '★ Make main', makeMainTitle: 'Windows plays here when HouseBeat is off or in direct mode',
    disconnected: 'Disconnected', notFound: 'Not found',
    directMeta: 'Live: the music already plays here, only the test beep is added',
    mainOutput: 'Main PC output', windowsOutput: 'Windows output',
    instant: 'Plays <b>instantly</b>',
    outTotal: 'Plays <b>{total}</b> late = {added} added{trim}',
    outTrim: ' + {trim} from the device',
    castTotal: 'Plays <b>{total}</b> late = {device} from the device + {added} added',
    measuring: 'Measuring…', off: 'Off',
    help: 'Cast devices are measured and aligned automatically. Whatever HouseBeat cannot measure (TV processing, distance and especially <b>Bluetooth speakers</b>, which add 150–300 ms) is tuned by ear with <b>Trim</b>: press <b>Test beep</b> and raise the trim of the speaker that sounds late (start at +150 ms for Bluetooth). A Bluetooth speaker shows up here as soon as you connect it in Windows. Lowering the delay of a Cast device reconnects it (2–3 s gap).',
    closedTitle: 'HouseBeat closed', closedText: 'The sound is back on your main output.',
    log: {
      capturing: 'Capturing from {dev}',
      capture_error: 'Capture error on {dev}: {err}',
      output_started: 'Playing on {dev}',
      output_direct: 'Playing on {dev} (live, beep only)',
      output_error: 'Error on output {dev}: {err}',
      outputs_error: 'Error checking outputs: {err}',
      default_restored: 'Windows switched the output to {dev}; moved it back to the virtual device',
      searching: 'Looking for Cast devices…',
      found: 'Found {name} ({host})',
      connect_failed: 'Cannot connect to {name}: {err}',
      casting: 'Streaming to {name}',
      cast_error: 'Error streaming to {name}: {err}',
      stopped: 'Stopped {name}',
      stop_error: 'Error stopping {name}: {err}',
      taken_over: '{name} is being used by another app; disabled it',
      relaunch: '{name} stopped; relaunching',
      watchdog_error: 'Watchdog {name}: {err}',
      sync_nothing: 'Auto-sync: nothing is on yet',
      sync_done: 'Auto-sync: everything at {target}s ({items})',
      mode_sync: 'Synced mode: Windows plays into {dev}',
      mode_direct: 'Direct mode: Windows plays on {dev}',
      mode_error: 'Error changing the audio output: {err}',
      no_virtual: 'No virtual audio device: install VB-CABLE to use synced mode',
      all_on: 'Everything on',
      all_off: 'Everything off',
      panel_at: 'Panel at {url}',
    },
  },
  es: {
    tagline: 'El audio de tu PC en todos los altavoces de casa, sincronizado.',
    theme: 'Tema', themeAuto: 'Auto', themeLight: 'Claro', themeDark: 'Oscuro',
    language: 'Idioma', langAuto: 'Auto',
    allOn: '⏻ Todo encendido', allOff: '⏻ Todo apagado',
    masterVolume: 'Volumen general',
    testBeep: '🔔 Pitido de prueba', testBeepTitle: 'Un pitido corto cada segundo durante 20 s para cuadrar los altavoces de oído',
    autoSync: '⚖ Auto-sincronizar', autoSyncTitle: 'Mide el retraso de cada altavoz y los iguala al más lento',
    search: '🔍 Buscar altavoces',
    mode: 'Modo:',
    modeSync: '🎯 Sincronizado', modeSyncTitle: 'Todo el audio de Windows pasa por HouseBeat, así este PC también se puede retrasar',
    modeDirect: '⚡ Directo', modeDirectTitle: 'Este PC suena al instante; solo se retrasan los demás altavoces',
    quit: '⏻ Salir', quitTitle: 'Devuelve el sonido a tu salida principal y cierra HouseBeat',
    offBanner: 'HouseBeat está apagado: tu PC suena como siempre. Enciéndelo todo para que suene en tus altavoces.',
    noVirtual: 'No hay ningún dispositivo de audio virtual, así que el modo sincronizado no está disponible. Instala el driver gratuito <a href="https://vb-audio.com/Cable/" target="_blank" rel="noopener">VB-CABLE</a> y reinicia HouseBeat.',
    volume: 'Volumen', added: 'Añadido', addedTitle: 'Retardo extra que mete HouseBeat para esperar al altavoz más lento',
    trim: 'Corrección', trimTitle: 'Lo que este altavoz tarda de más después de lo que HouseBeat puede medir (tele, Bluetooth, distancia). Si suena tarde, súbelo; si suena antes, bájalo. Se re-sincroniza solo.',
    soundsLate: 'suena tarde', soundsEarly: 'suena antes',
    format: 'Formato', formatTitle: 'WAV pesa más, pero algunos aparatos empiezan antes con él',
    mp3: 'MP3 (ligero)', wav: 'WAV (sin comprimir)',
    reconnect: '↻ Reconectar', makeMain: '★ Hacer principal', makeMainTitle: 'Windows suena aquí cuando HouseBeat está apagado o en modo directo',
    disconnected: 'Desconectado', notFound: 'No encontrado',
    directMeta: 'En directo: la música ya suena aquí, solo se añade el pitido de prueba',
    mainOutput: 'Salida principal del PC', windowsOutput: 'Salida de Windows',
    instant: 'Suena <b>al instante</b>',
    outTotal: 'Suena <b>{total}</b> tarde = {added} añadidos{trim}',
    outTrim: ' + {trim} del aparato',
    castTotal: 'Suena <b>{total}</b> tarde = {device} del aparato + {added} añadidos',
    measuring: 'Midiendo…', off: 'Apagado',
    help: 'Los Chromecast se miden y sincronizan solos. Lo que HouseBeat no puede medir (la tele, la distancia y sobre todo los <b>altavoces Bluetooth</b>, que tardan 150–300 ms) se ajusta de oído con <b>Corrección</b>: pulsa <b>Pitido de prueba</b> y sube la corrección del que suene tarde (en un Bluetooth empieza por +150 ms). Un altavoz Bluetooth aparece aquí en cuanto lo conectas en Windows. Al bajar el retardo de un Chromecast se reconecta (2–3 s de corte).',
    closedTitle: 'HouseBeat cerrado', closedText: 'El sonido ha vuelto a tu salida principal.',
    log: {
      capturing: 'Capturando de {dev}',
      capture_error: 'Error capturando de {dev}: {err}',
      output_started: 'Sonando en {dev}',
      output_direct: 'Sonando en {dev} (directo, solo pitido)',
      output_error: 'Error en la salida {dev}: {err}',
      outputs_error: 'Error revisando salidas: {err}',
      default_restored: 'Windows cambió la salida a {dev}; la devuelvo al dispositivo virtual',
      searching: 'Buscando Chromecasts…',
      found: 'Encontrado {name} ({host})',
      connect_failed: 'No conecta con {name}: {err}',
      casting: 'Enviando a {name}',
      cast_error: 'Error enviando a {name}: {err}',
      stopped: 'Parado {name}',
      stop_error: 'Error parando {name}: {err}',
      taken_over: '{name} lo está usando otra app; lo desactivo',
      relaunch: '{name} parado; relanzo',
      watchdog_error: 'Vigilancia {name}: {err}',
      sync_nothing: 'Auto-sincronizar: todavía no hay nada encendido',
      sync_done: 'Auto-sincronizar: todo a {target}s ({items})',
      mode_sync: 'Modo sincronizado: Windows suena por {dev}',
      mode_direct: 'Modo directo: Windows suena por {dev}',
      mode_error: 'Error cambiando la salida de audio: {err}',
      no_virtual: 'No hay dispositivo de audio virtual: instala VB-CABLE para usar el modo sincronizado',
      all_on: 'Todo encendido',
      all_off: 'Todo apagado',
      panel_at: 'Panel en {url}',
    },
  },
};

function pickLang() {
  const forced = new URLSearchParams(location.search).get('lang') || localStorage.getItem('hb-lang');
  if (forced && STRINGS[forced]) return forced;
  return (navigator.language || 'en').toLowerCase().startsWith('es') ? 'es' : 'en';
}

let LANG = pickLang();

function fill(text, params) {
  return text.replace(/\{(\w+)\}/g, (_, k) => (params && k in params ? params[k] : `{${k}}`));
}

function t(key, params) {
  const text = STRINGS[LANG][key] ?? STRINGS.en[key] ?? key;
  return fill(text, params);
}

function tLog(entry) {
  const text = STRINGS[LANG].log[entry.k] ?? STRINGS.en.log[entry.k] ?? entry.k;
  return `${entry.t} ${fill(text, entry.p)}`;
}

// Static texts: data-i18n (text), data-i18n-html (markup), data-i18n-title (tooltip)
function applyStaticTexts() {
  document.documentElement.lang = LANG;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-html]').forEach(el => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll('[data-i18n-title]').forEach(el => { el.title = t(el.dataset.i18nTitle); });
}
