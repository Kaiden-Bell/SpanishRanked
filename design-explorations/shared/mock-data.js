/* Mock content for the Language AI concept prototypes.
   Rank thresholds, XP amounts and streak multipliers mirror src/backend/app/rules.py.
   Everything else (vocabulary, scenes, sample sessions) is synthetic demo data. */
window.MOCK = {
  user: { name: 'Kaiden' },

  ranks: [
    [0, 'Pre-Learner I'], [120, 'Pre-Learner II'], [300, 'Pre-Learner III'],
    [550, 'Learner I'], [900, 'Learner II'], [1300, 'Learner III'],
  ],
  streakMultipliers: [[30, 1.20], [14, 1.15], [7, 1.10], [3, 1.05], [1, 1.00]],
  rules: { base: 15, minutesPerBonus: 2, sessionCap: 45, quizPerCorrect: 3, dailyCapStudy: 100, dailyCapAssess: 30 },

  // Placeholder environments. `s1..s3` tint the gradient block; swap `photo` for a real file later.
  scenes: [
    { id: 'granada', place: 'Granada', title: 'The Alhambra at dusk', photo: null, s1: '#2b2f3a', s2: '#8a6a4a', s3: '#c28a5a' },
    { id: 'barcelona', place: 'Barcelona', title: 'A quiet street in El Born, early morning', photo: null, s1: '#1f2a33', s2: '#5d6f78', s3: '#c9b48f' },
    { id: 'salamanca', place: 'Salamanca', title: 'The old university library', photo: null, s1: '#2a1f18', s2: '#6b4a2f', s3: '#b88a4f' },
    { id: 'cantabria', place: 'Cantabria', title: 'Green hills above the northern coast', photo: null, s1: '#18262a', s2: '#3f6a5c', s3: '#9fb59a' },
    { id: 'sevilla', place: 'Sevilla', title: 'A courtyard with orange trees', photo: null, s1: '#2a2218', s2: '#7c6a3a', s3: '#d0a95c' },
  ],

  activityTypes: [
    'Watching a show or film', 'Listening to music', 'Reading a book or article',
    'Textbook or workbook', 'Conversation', 'Writing practice', 'Other',
  ],
  guidedFocus: [
    'Everyday verbs with reflexive pronouns', 'Subjunctive after aunque and ojalá',
    'Food, meals and restaurants', 'Talking about time and waiting',
  ],

  // Seed vocabulary: what the learner has already logged.
  vocab: [
    { id: 'v1', es: 'esperar', en: 'to wait; to hope', pos: 'verb', example: 'Te espero en la plaza a las ocho.', exampleEn: 'I will wait for you in the square at eight.', source: 'La Casa de Papel, S2E3', learnerSentence: 'Espero el autobús todos los días.', seen: 4, status: 'recalled' },
    { id: 'v2', es: 'quedarse', en: 'to stay; to be left', pos: 'verb (reflexive)', example: 'Me quedo en casa esta noche.', exampleEn: 'I am staying home tonight.', source: 'Duolingo podcast', learnerSentence: 'Me quedo aquí con mis amigos.', seen: 3, status: 'recalled' },
    { id: 'v3', es: 'ponerse', en: 'to put on; to become', pos: 'verb (reflexive)', example: 'Se puso nervioso antes del examen.', exampleEn: 'He got nervous before the exam.', source: 'Textbook, unit 9', learnerSentence: 'Me pongo la chaqueta porque hace frío.', seen: 2, status: 'seen' },
    { id: 'v4', es: 'la sobremesa', en: 'time spent talking at the table after a meal', pos: 'noun (f)', example: 'La sobremesa duró dos horas.', exampleEn: 'The after-meal conversation lasted two hours.', source: 'Travel blog, Valencia', learnerSentence: 'Me gusta la sobremesa con mi familia.', seen: 2, status: 'seen' },
    { id: 'v5', es: 'la madrugada', en: 'the early hours, small hours', pos: 'noun (f)', example: 'Llegamos a casa de madrugada.', exampleEn: 'We got home in the early hours.', source: 'Song: Madrugada', learnerSentence: 'Estudio en la madrugada.', seen: 1, status: 'new' },
    { id: 'v6', es: 'aunque', en: 'although; even if', pos: 'conjunction', example: 'Aunque llueva, vamos a salir.', exampleEn: 'Even if it rains, we are going out.', source: 'Textbook, unit 11', learnerSentence: 'Aunque estoy cansado, estudio.', seen: 3, status: 'seen', note: 'Takes the subjunctive when the outcome is uncertain.' },
    { id: 'v7', es: 'echar de menos', en: 'to miss (someone)', pos: 'phrase', example: 'Echo de menos a mi hermana.', exampleEn: 'I miss my sister.', source: 'Conversation with Marta', learnerSentence: 'Echo de menos mi ciudad.', seen: 2, status: 'recalled' },
    { id: 'v8', es: 'tardar', en: 'to take (time)', pos: 'verb', example: '¿Cuánto tardas en llegar?', exampleEn: 'How long does it take you to get there?', source: 'La Casa de Papel, S2E5', learnerSentence: 'Tardo veinte minutos en el trabajo.', seen: 2, status: 'seen' },
    { id: 'v9', es: 'enterarse', en: 'to find out', pos: 'verb (reflexive)', example: 'Me enteré de la noticia ayer.', exampleEn: 'I found out about the news yesterday.', source: 'News podcast', learnerSentence: 'Me entero de todo por mi madre.', seen: 1, status: 'new' },
    { id: 'v10', es: 'ojalá', en: 'I hope; if only', pos: 'interjection', example: 'Ojalá que mañana haga sol.', exampleEn: 'I hope it is sunny tomorrow.', source: 'Song: Ojalá', learnerSentence: 'Ojalá que llegue pronto.', seen: 2, status: 'seen', note: 'Always followed by the subjunctive.' },
    { id: 'v11', es: 'hacerse', en: 'to become (by effort)', pos: 'verb (reflexive)', example: 'Se hizo médico a los treinta años.', exampleEn: 'He became a doctor at thirty.', source: 'Textbook, unit 9', learnerSentence: 'Quiero hacerme profesor.', seen: 1, status: 'new' },
    { id: 'v12', es: 'desde luego', en: 'of course; certainly', pos: 'phrase', example: 'Desde luego, tienes razón.', exampleEn: 'Of course, you are right.', source: 'Conversation with Marta', learnerSentence: 'Desde luego que voy a la fiesta.', seen: 2, status: 'recalled' },
  ],

  // Seed evidence for the two written modalities. Listening and speaking have none:
  // Level 1 does not evaluate them, so the UI says "Not yet assessed".
  skills: { reading: { assessed: 14, hits: 10 }, writing: { assessed: 11, hits: 5 }, listening: null, speaking: null },
  seedXp: 212,
};
