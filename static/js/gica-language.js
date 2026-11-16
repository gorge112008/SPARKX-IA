/* Agent vocatives only. Never rewrite a person's name inside a search query. */
const unsafe = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/u;
const prefix = /^((?:(?:hola|oye|buenos? d[ií]as?|buenas tardes|buenas noches|buenas|saludos|hey|ahora|ahorita|en este momento|por favor)[, ]+)*)(gica|jica|yica|yika|llica|ilica|chica)(?:-1| (?:uno|1))?([, ]+)(.+)$/iu;
const suffix = /([,;])\s*(?:gica|jica|yica|yika|llica|ilica|chica)(?:-1| (?:uno|1))?([.!¡?¿]*)$/iu;
const alone = /^((?:(?:hola|oye|buenos? d[ií]as?|buenas tardes|buenas noches|buenas|saludos|hey|ahora|ahorita|en este momento|por favor)[, ]+)*)(?:gica|jica|yica|yika|llica|ilica|chica)(?:-1| (?:uno|1))?([.!¡?¿]*)$/iu;
const commandStart = /^(?:abre|abrir|[aá]breme|muestra|mu[eé]strame|mostrar|visualiza|visualizar|quiero|quisiera|necesito|puedes|podr[ií]as|ve|ir|ll[eé]vame|llevar|entra|entrar|navega|navegar|haz clic|hacer clic|haz click|hacer click|pulsa|pulsar|presiona|presionar|dir[ií]gete|busca|buscar|b[uú]squeda|encuentra|ubica|localiza|pon|poner|cambia|cambiar|establece|ajusta|selecciona|activa|aplica|calendario|directorio|eventos|contactos|lista|listado|agenda|programa|cronograma|modo|tema|hablemos|ejecuta|cancela|silencio|deja)\b/iu;

export function normalizeAgentReference(text, context = '') {
  if (typeof text !== 'string' || text.length > 300 || unsafe.test(text)) return text;
  let value = text.normalize('NFC');
  if (context === 'person_name') return value;
  if (/[<>"'`«»“”‘’\\/{}\[\]]|\b(?:https?|ftp|file|data|javascript|mailto):|www\./iu.test(value)) return value;
  if (context === 'confirmation') {
    value = value.replace(/^(s[ií]|no)([, ]+)(?:gica|jica|yica|yika|llica|ilica|chica)(?:-1| (?:uno|1))?(?=[, .!¡?¿]|$)/iu, '$1$2Gica');
    value = value.replace(/^(?:gica|jica|yica|yika|llica|ilica|chica)(?:-1| (?:uno|1))?([, ]+)(s[ií]|no)(?=[, .!¡?¿]|$)/iu, 'Gica$1$2');
  }
  if (alone.test(value)) return value.replace(alone, '$1Gica$2');
  const match = value.match(prefix);
  if (match && commandStart.test(match[4])) value = `${match[1]}Gica${match[3]}${match[4]}`;
  // A suffix requires a comma, so "busca a Yika" is a person's name, not a vocative.
  if (suffix.test(value)) value = value.replace(suffix, '$1 Gica$2');
  return value;
}
