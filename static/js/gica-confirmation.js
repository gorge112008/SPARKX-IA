/* Pure, bounded confirmation vocabulary. Not an action interpreter. */
const unsafe = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
const uncertainty = new Set(['quiza', 'quizas', 'depende', 'creo', 'supongo', 'posiblemente', 'probablemente', 'dudo', 'duda',
  'dudas', 'talvez', 'acaso', 'pero', 'aunque', 'todavia', 'espera', 'esperate', 'nunca', 'jamas']);
const reported = new Set(['dijo', 'dijeron', 'dije', 'dices', 'dice', 'dicen', 'decir', 'decia', 'diria', 'dijera', 'dijese',
  'pregunto', 'preguntaron', 'pregunte', 'pregunta', 'leyo', 'escribio', 'escribi', 'menciono', 'comento', 'conto', 'afirmo',
  'cita', 'citado', 'citada', 'frase', 'ejemplo', 'texto', 'repite', 'imita', 'supongamos', 'hipoteticamente',
  'diga', 'digas', 'digan', 'dijiste', 'afirme', 'afirmara']);
const conditions = new Set(['cuando', 'entonces', 'fuera', 'fueras', 'fuese', 'pudiera', 'pudieras', 'hubiera', 'hubiese',
  'tuviera', 'tuvieras', 'condicion', 'condicional', 'siempre', 'excepto', 'menos', 'dependeria']);
const otherActions = new Set(['abre', 'abrir', 'muestra', 'muestrame', 'mostrar', 'busca', 'buscar', 'busqueda', 'encuentra',
  'llevame', 'cambia', 'cambiar', 'pon', 'poner', 'crea', 'crear', 'elimina', 'eliminar', 'borra', 'borrar', 'agrega', 'anade',
  'guarda', 'guardar', 'envia', 'enviar', 'administra', 'configura', 'autoriza', 'aprueba', 'actualiza', 'asigna', 'modifica',
  'edita', 'paga', 'compra', 'navega', 'calendario', 'directorio', 'evento', 'eventos', 'persona', 'usuarios', 'permisos',
  'api', 'clave', 'claves', 'modelo', 'admin', 'administrador', 'archivo', 'correo', 'tema', 'modo', 'oscuro', 'oscura', 'sesion']);
const affirmative = new Set(['adelante', 'perfecto', 'perfecta', 'encanta', 'supuesto', 'acuerdo', 'hazlo', 'ejecutalo',
  'confirmo', 'confirmado', 'procede', 'favor', 'claro', 'ok', 'okay', 'correcto', 'genial', 'excelente', 'bueno', 'bien',
  'gusto', 'acepto', 'afirmativo', 'vale', 'gica', 'jica', 'yica', 'yika', 'llica', 'ilica']);
const cancellation = new Set(['cancela', 'cancelalo', 'cancelar', 'cancelacion', 'deten', 'detenlo', 'detener',
  'rechaza', 'rechazalo', 'evita', 'evitalo', 'deshaz', 'descarta', 'descartalo', 'suspende', 'suspendelo']);

export function classifyConfirmation(text) {
  if (typeof text !== 'string' || !text.trim() || text.length > 300 || unsafe.test(text)) return 'ambiguous';
  const plain = text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  if (/["'«»“”‘’`<>¿?]/u.test(plain) || /[^\p{L}\p{N}\s.,!¡:;…-]/u.test(plain)) return 'ambiguous';
  const tokens = plain.match(/[\p{L}\p{N}]+/gu) || [];
  const originalTokens = text.normalize('NFC').toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
  const yes = tokens.includes('si'), no = tokens.includes('no');
  if (yes && no) return 'ambiguous';
  if (tokens.some(token => uncertainty.has(token) || reported.has(token) || conditions.has(token)) ||
      /\btal\s+vez\b|\bno\s+(?:estoy|es|parece)\s+segur[oa]\b/u.test(plain)) return 'ambiguous';
  if (!yes && !no) return 'request';
  // A complete positive/negative word is necessary; accompaniment is natural
  // language, while another action, quoted/reporting speech and conditions stop it.
  if (tokens.length > 45 || tokens.some(token => otherActions.has(token)) ||
      (yes && tokens.some(token => cancellation.has(token))) ||
      /\bsi\s+(?:puedes|podemos|puedo|hay|tienes|tiene|funciona|sirve|sucede|ocurre|necesitas|quieres|es|esta|mi|mis|tu|tus|su|sus|el|la|los|las|esto|eso|todo|todos|todas|algo|alguien|nadie|un|una)\b/u.test(plain) ||
      /\bsi\s+(?:lo|te|le|me|nos|les)\s+(?:deseas|quieres|prefieres|necesitas|consideras|conviene|sirve|gusta)\b/u.test(plain)) return 'ambiguous';
  // Unaccented "si" can also introduce a condition. Require a positive cue in
  // an expanded reply; the standalone word remains an explicit confirmation.
  if (yes && tokens.length > 1 && !originalTokens.includes('sí') && !tokens.some(token => affirmative.has(token))) return 'ambiguous';
  return yes ? 'yes' : 'no';
}
