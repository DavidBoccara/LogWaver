/**
 * Génère la présentation de LogWaver (docs/LogWaver_Presentation.pptx).
 *
 * Outil de documentation uniquement (Node.js) :
 *   npm install pptxgenjs react react-dom react-icons sharp
 *   node tools/doc/generer_presentation.js
 * Les captures d'écran proviennent de docs/images (tools/doc/captures_ecran.py).
 */
"use strict";

const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const ROOT = path.resolve(__dirname, "..", "..");
const IMAGES = path.join(ROOT, "docs", "images");
const OUTPUT = path.join(ROOT, "docs", "LogWaver_Presentation.pptx");
const fs = require("fs");
// Version lue à la source unique (logwaver/__init__.py).
const VERSION = fs.readFileSync(path.join(ROOT, "logwaver", "__init__.py"), "utf8")
  .match(/__version__\s*=\s*"([^"]+)"/)[1];

// Palette reprise de l'application : bleu marine dominant, vert de l'action « Justifier ».
const COLOR = {
  navy: "2F4F6F", deep: "1F3448", blue: "2F6FB0", green: "2E9D4F", amber: "E0A000",
  red: "D03B3B", grey: "5F6B76", light: "EEF3F8", line: "C9D1D9", text: "1F2933",
  white: "FFFFFF", ice: "CFE1F5",
};
const FONT = "Calibri";
const W = 13.333;
const H = 7.5;

/** Dimensions (px) des captures, pour respecter leurs proportions. */
const SHOTS = {
  accueil: ["01_accueil.png", 1500, 880], groupe: ["02_liste_groupee.png", 1500, 880],
  details: ["03_liste_details.png", 1500, 880], justifier: ["04_justifier.png", 560, 537],
  ia: ["05_aide_ia.png", 900, 720], didacticiel: ["06_didacticiel.png", 1572, 880],
  editeur: ["07_editeur_plugin.png", 1250, 820], assistant: ["08_assistant_elements.png", 980, 700],
  verification: ["09_assistant_verification.png", 980, 700],
  regles: ["10_regles_correspondance.png", 940, 940],
};

/** Rend une icône react-icons en PNG base64 (blanche, 256 px). */
async function icon(Component, color = "#FFFFFF") {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Component, { color, size: 256 }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

/** Ajoute une capture en conservant ses proportions dans le cadre donné. */
function addShot(slide, key, box, name) {
  const [file, pw, ph] = SHOTS[key];
  const ratio = pw / ph;
  let w = box.w;
  let h = w / ratio;
  if (h > box.h) { h = box.h; w = h * ratio; }
  const x = box.x + (box.w - w) / 2;
  const y = box.y + (box.h - h) / 2;
  slide.addImage({
    path: path.join(IMAGES, file), x, y, w, h, objectName: name, altText: name,
    shadow: { type: "outer", color: "000000", opacity: 0.25, blur: 8, offset: 3, angle: 90 },
  });
}

/** Pastille ronde colorée contenant une icône (motif visuel du deck). */
function addBadge(slide, data, x, y, size, fill, name) {
  slide.addShape("ellipse", { x, y, w: size, h: size, fill: { color: fill },
                              line: { color: fill }, objectName: `${name} - pastille` });
  const pad = size * 0.24;
  slide.addImage({ data, x: x + pad, y: y + pad, w: size - 2 * pad, h: size - 2 * pad,
                   objectName: `${name} - icône` });
}

/** Bloc titre + texte (puces facultatives). */
function addTextBlock(slide, x, y, w, h, heading, lines, name, opts = {}) {
  const runs = [{ text: heading, options: { bold: true, fontSize: opts.headSize || 17,
                                            color: opts.headColor || COLOR.navy,
                                            breakLine: true, paraSpaceAfter: 4 } }];
  lines.forEach((line, i) => runs.push({
    text: line,
    options: { fontSize: opts.size || 14, color: opts.color || COLOR.text,
               bullet: opts.bullets ? { indent: 14 } : false,
               breakLine: i < lines.length - 1, paraSpaceAfter: 5 },
  }));
  slide.addText(runs, { x, y, w, h, valign: "top", margin: 0, isTextBox: true,
                        objectName: name, fontFace: FONT });
}

function defineLayouts(pres) {
  pres.defineSlideMaster({
    title: "TITRE_SOMBRE",
    background: { color: COLOR.deep },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.7, y: 2.0, w: 6.2, h: 1.6,
                                  fontFace: FONT, fontSize: 48, bold: true, color: COLOR.white,
                                  align: "left", valign: "bottom", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.7, y: 3.75, w: 6.0, h: 1.6,
                                  fontFace: FONT, fontSize: 20, color: COLOR.ice,
                                  align: "left", valign: "top", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "CONTENU",
    background: { color: COLOR.white },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.85,
                                  fontFace: FONT, fontSize: 34, bold: true, color: COLOR.navy,
                                  valign: "middle", margin: 0 }, text: "" } },
      { text: { text: `LogWaver ${VERSION}`, options: { x: 0.6, y: 7.0, w: 4, h: 0.3,
                fontFace: FONT, fontSize: 10, color: COLOR.grey, margin: 0 } } },
    ],
    slideNumber: { x: 12.2, y: 7.0, w: 0.5, h: 0.3, fontFace: FONT, fontSize: 10,
                   color: COLOR.grey, align: "right" },
  });
}

async function build() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = "LogWaver — présentation";
  pres.author = "LogWaver";
  pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
  defineLayouts(pres);

  const ic = {
    plug: await icon(fa.FaPlug), check: await icon(fa.FaCheckCircle),
    share: await icon(fa.FaShareAlt), folder: await icon(fa.FaFolderOpen),
    save: await icon(fa.FaSave), layers: await icon(fa.FaLayerGroup),
    robot: await icon(fa.FaRobot), book: await icon(fa.FaBookOpen),
    code: await icon(fa.FaCode), magic: await icon(fa.FaMagic),
    graduate: await icon(fa.FaGraduationCap), balance: await icon(fa.FaBalanceScale),
    flask: await icon(fa.FaFlask), user: await icon(fa.FaUserEdit),
  };

  // 1 ── Titre ------------------------------------------------------------------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "TITRE_SOMBRE", sectionTitle: "Introduction" });
  s.addText("LogWaver", { placeholder: "title" });
  s.addText("Suivre et justifier les notes, warnings et erreurs de n'importe quel outil",
            { placeholder: "body" });
  s.addText(`Version ${VERSION}`, { x: 0.7, y: 5.6, w: 4, h: 0.4, fontFace: FONT, fontSize: 14,
                                    color: COLOR.ice, margin: 0, isTextBox: true,
                                    objectName: "Version" });
  addShot(s, "details", { x: 7.2, y: 1.2, w: 5.6, h: 5.1 }, "Capture fenêtre principale");
  s.addNotes("LogWaver lit le log de n'importe quel outil, en extrait les éléments et permet de "
             + "les justifier une fois pour toutes. Les justifications se réappliquent toutes "
             + "seules aux logs suivants et se transmettent d'un concepteur à l'autre.");

  // 2 ── La promesse ------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Introduction" });
  s.addText("Justifié une fois, suivi pour toujours", { placeholder: "title" });
  const promises = [
    [ic.plug, COLOR.blue, "N'importe quel outil",
     "Un plugin décrit le format du log. L'outil est reconnu tout seul, par l'extension du "
     + "fichier ou par son contenu."],
    [ic.check, COLOR.green, "Justifié une fois",
     "Chaque élément est classé (Justifié, Rejeté…) avec une explication signée. Le prochain "
     + "log reprend automatiquement ces justifications."],
    [ic.share, COLOR.amber, "Transmis à un collègue",
     "Le concepteur B récupère les justifications du concepteur A : il ne lui reste que les "
     + "éléments vraiment nouveaux."],
  ];
  promises.forEach(([img, color, head, text], i) => {
    const x = 0.6 + i * 4.15;
    s.addShape("roundRect", { x, y: 2.0, w: 3.85, h: 3.9, rectRadius: 0.12,
                              fill: { color: COLOR.light }, line: { color: COLOR.light },
                              objectName: `Carte ${head}` });
    addBadge(s, img, x + 0.35, 2.35, 1.0, color, head);
    addTextBlock(s, x + 0.35, 3.6, 3.15, 2.1, head, [text], `Texte ${head}`,
                 { headSize: 20, size: 15 });
  });
  s.addNotes("Trois promesses : n'importe quel outil grâce aux plugins, une justification faite "
             + "une seule fois, et un suivi qui se transmet entre concepteurs.");

  // 3 ── En 3 gestes -------------------------------------------------------------
  pres.addSection({ title: "Utilisation" });
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Utilisation" });
  s.addText("Trois gestes pour démarrer", { placeholder: "title" });
  const steps = [
    [ic.folder, "1. Ouvrir un log", "Le plugin est choisi automatiquement."],
    [ic.check, "2. Justifier", "Un élément, une sélection ou un groupe entier."],
    [ic.save, "3. Enregistrer", "Puis exporter vers Excel ou Word."],
  ];
  steps.forEach(([img, head, text], i) => {
    const y = 1.65 + i * 1.65;
    addBadge(s, img, 0.6, y, 0.95, [COLOR.blue, COLOR.green, COLOR.navy][i], head);
    addTextBlock(s, 1.8, y + 0.05, 3.6, 1.3, head, [text], `Étape ${head}`,
                 { headSize: 20, size: 15 });
  });
  addShot(s, "accueil", { x: 5.6, y: 1.5, w: 7.1, h: 5.2 }, "Capture page d'accueil");
  s.addNotes("La page d'accueil reprend ces trois gestes. Un bandeau « À faire » indique ensuite "
             + "en permanence la prochaine action et ce qu'il reste à justifier.");

  // 4 ── Regrouper ----------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Utilisation" });
  s.addText("Regrouper pour justifier en masse", { placeholder: "title" });
  addShot(s, "groupe", { x: 0.6, y: 1.45, w: 7.9, h: 5.3 }, "Capture liste groupée");
  addBadge(s, ic.layers, 8.95, 1.6, 0.8, COLOR.blue, "Regrouper");
  addTextBlock(s, 8.95, 2.6, 3.8, 4.2, "Un groupe = un clic",
               ["« Regrouper par » : code, fichier, message identique, type, auteur… ou tout "
                + "champ du plugin",
                "Chaque groupe se replie et affiche ce qu'il reste à justifier",
                "Sélectionner le groupe sélectionne tous ses éléments : « Justifier » les traite "
                + "ensemble"],
               "Texte regroupement", { bullets: true, size: 15 });
  s.addNotes("Exemple : regrouper par fichier puis sélectionner un fichier tiers justifie d'un coup "
             + "tous ses warnings.");

  // 5 ── Justifier -----------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Utilisation" });
  s.addText("Justifier : quoi, pourquoi, par qui", { placeholder: "title" });
  addShot(s, "justifier", { x: 0.6, y: 1.45, w: 5.4, h: 5.3 }, "Capture fenêtre Justifier");
  const cats = [["Rejeté", COLOR.red, "50"], ["En cours d'analyse", COLOR.blue, "40"],
                ["À traiter", COLOR.amber, "30"], ["Justifié / Accepté", COLOR.green, "20"],
                ["Clôturé", COLOR.grey, "10"]];
  s.addText("Catégories configurables et leur priorité", {
    x: 6.6, y: 1.55, w: 6.1, h: 0.45, fontFace: FONT, fontSize: 18, bold: true,
    color: COLOR.navy, margin: 0, isTextBox: true, objectName: "Titre catégories" });
  cats.forEach(([label, color, prio], i) => {
    const y = 2.2 + i * 0.62;
    s.addShape("roundRect", { x: 6.6, y, w: 4.3, h: 0.5, rectRadius: 0.08, fill: { color },
                              line: { color }, objectName: `Catégorie ${label}` });
    s.addText(label, { x: 6.75, y, w: 4.0, h: 0.5, fontFace: FONT, fontSize: 15, bold: true,
                       color: COLOR.white, valign: "middle", margin: 0, isTextBox: true,
                       objectName: `Libellé ${label}` });
    s.addText(`priorité ${prio}`, { x: 11.05, y, w: 1.65, h: 0.5, fontFace: FONT, fontSize: 14,
                                     color: COLOR.grey, valign: "middle", margin: 0,
                                     isTextBox: true, objectName: `Priorité ${label}` });
  });
  addTextBlock(s, 6.6, 5.4, 6.1, 1.4, "Traçabilité",
               ["Nom de l'auteur demandé une seule fois · Ctrl+Z / Ctrl+Y sur tout · "
                + "retrait possible à tout moment"],
               "Texte traçabilité", { size: 14 });
  s.addNotes("La priorité sert lors des imports : un « Rejeté » reçu d'un collègue remplace un "
             + "« Justifié » ; à priorité égale, la justification existante est conservée.");

  // 6 ── Suivi entre concepteurs --------------------------------------------------------
  pres.addSection({ title: "Suivi" });
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Suivi" });
  s.addText("Le suivi passe d'un concepteur à l'autre", { placeholder: "title" });
  const flow = [["Concepteur A", "justifie ses warnings", COLOR.blue, ic.user],
                ["Fichier .lwj", "« Partager mes justifications »", COLOR.amber, ic.share],
                ["Concepteur B", "ne voit que le nouveau", COLOR.green, ic.check]];
  flow.forEach(([head, text, color, img], i) => {
    const x = 0.8 + i * 4.2;
    addBadge(s, img, x + 1.05, 1.75, 1.25, color, head);
    s.addText([{ text: head, options: { bold: true, fontSize: 20, color: COLOR.navy,
                                        breakLine: true } },
               { text, options: { fontSize: 15, color: COLOR.text } }],
              { x, y: 3.15, w: 3.4, h: 0.95, align: "center", margin: 0, fontFace: FONT,
                isTextBox: true, objectName: `Flux ${head}` });
    if (i < 2) {
      s.addShape("rightArrow", { x: x + 3.45, y: 2.1, w: 0.65, h: 0.55,
                                 fill: { color: COLOR.line }, line: { color: COLOR.line },
                                 objectName: `Flèche ${i + 1}` });
    }
  });
  s.addShape("roundRect", { x: 0.8, y: 4.6, w: 11.7, h: 1.65, rectRadius: 0.1,
                            fill: { color: COLOR.light }, line: { color: COLOR.light },
                            objectName: "Cadre exemple" });
  addTextBlock(s, 1.15, 4.8, 11.0, 1.35, "Sur l'exemple fourni",
               ["Les éléments que B partage avec A arrivent déjà justifiés : seuls les "
                + "nouveaux (theme.qss, fuite mémoire…) restent à traiter",
                "Un projet .lwp complet peut aussi être importé ; les conflits sont résolus par "
                + "priorité, et l'import s'annule par Ctrl+Z"],
               "Texte exemple suivi", { bullets: true, size: 15 });
  s.addNotes("C'est le cœur de l'outil : le concepteur B hérite des justifications du concepteur "
             + "A pour le code qu'il réutilise.");

  // 7 ── Règles de correspondance --------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Suivi" });
  s.addText("Retrouver une justification malgré les différences", { placeholder: "title" });
  addShot(s, "regles", { x: 0.6, y: 1.45, w: 5.4, h: 5.35 }, "Capture règles de correspondance");
  const presets = [["Strict", "tout identique, ligne comprise"],
                   ["Recommandé", "la ligne et le dossier peuvent changer"],
                   ["Tolérant", "nombres et noms cités dans le message ignorés"],
                   ["Par code", "une justification vaut pour tout le code"]];
  addBadge(s, ic.balance, 6.6, 1.6, 0.8, COLOR.amber, "Règles");
  s.addText("Ctrl+M : choisir ce qui doit être identique", {
    x: 7.6, y: 1.6, w: 5.1, h: 0.8, fontFace: FONT, fontSize: 18, bold: true, color: COLOR.navy,
    valign: "middle", margin: 0, isTextBox: true, objectName: "Titre règles" });
  presets.forEach(([head, text], i) => {
    const y = 2.65 + i * 0.78;
    s.addShape("roundRect", { x: 6.6, y, w: 6.1, h: 0.65, rectRadius: 0.08,
                              fill: { color: COLOR.light }, line: { color: COLOR.light },
                              objectName: `Préréglage ${head}` });
    s.addText([{ text: `${head}  `, options: { bold: true, color: COLOR.navy } },
               { text, options: { color: COLOR.text } }],
              { x: 6.8, y, w: 5.8, h: 0.65, fontFace: FONT, fontSize: 15, valign: "middle",
                margin: 0, isTextBox: true, objectName: `Texte ${head}` });
  });
  s.addText("Aperçu immédiat : « Éléments justifiés : 2 → 3 (+1) », avec la liste des éléments "
            + "gagnés ou perdus. Aucune justification n'est jamais supprimée.", {
    x: 6.6, y: 5.85, w: 6.1, h: 0.9, fontFace: FONT, fontSize: 14, italic: true,
    color: COLOR.grey, margin: 0, isTextBox: true, objectName: "Texte aperçu" });
  s.addNotes("Exemple : en mode Tolérant, « le fichier dada.txt est introuvable » et « le fichier "
             + "theme.qss est introuvable » sont considérés comme le même problème.");

  // 8 ── Plugins et assistant regex -----------------------------------------------------------
  pres.addSection({ title: "Outils" });
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Outils" });
  s.addText("Créer un plugin sans écrire de regex", { placeholder: "title" });
  addShot(s, "assistant", { x: 5.4, y: 1.45, w: 7.3, h: 5.3 }, "Capture assistant regex");
  const wizard = ["Choisir le type (ex. Warning)", "Cliquer sur une ligne d'exemple",
                  "Surligner les éléments et les parties variables (date…)",
                  "Vérifier sur tout l'exemple"];
  addBadge(s, ic.magic, 0.6, 1.6, 0.8, COLOR.green, "Assistant");
  s.addText("Assistant pas à pas", { x: 1.6, y: 1.6, w: 3.6, h: 0.8, fontFace: FONT,
                                     fontSize: 20, bold: true, color: COLOR.navy, valign: "middle",
                                     margin: 0, isTextBox: true, objectName: "Titre assistant" });
  wizard.forEach((text, i) => {
    const y = 2.65 + i * 0.85;
    s.addShape("ellipse", { x: 0.6, y: y + 0.05, w: 0.5, h: 0.5, fill: { color: COLOR.navy },
                            line: { color: COLOR.navy }, objectName: `Numéro ${i + 1}` });
    s.addText(String(i + 1), { x: 0.6, y: y + 0.05, w: 0.5, h: 0.5, fontFace: FONT,
                               fontSize: 15, bold: true, color: COLOR.white, align: "center",
                               valign: "middle", margin: 0, isTextBox: true,
                               objectName: `Chiffre ${i + 1}` });
    s.addText(text, { x: 1.3, y, w: 3.9, h: 0.6, fontFace: FONT, fontSize: 15, color: COLOR.text,
                      valign: "middle", margin: 0, isTextBox: true,
                      objectName: `Étape assistant ${i + 1}` });
  });
  s.addText("Le texte non sélectionné sert de repère fixe : les éléments peuvent prendre "
            + "n'importe quelle valeur.", {
    x: 0.6, y: 6.1, w: 4.6, h: 0.7, fontFace: FONT, fontSize: 13, italic: true,
    color: COLOR.grey, margin: 0, isTextBox: true, objectName: "Texte invariant" });
  s.addNotes("Outils > Créer un nouveau plugin part de zéro. Les extensions de fichiers déclarées "
             + "(.log, .mx) associent ensuite automatiquement les logs au plugin.");

  // 9 ── Aide pour décider -------------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Outils" });
  s.addText("De l'aide pour décider", { placeholder: "title" });
  const helps = [
    [ic.robot, COLOR.blue, "Demander à l'IA",
     "Un prompt prêt à l'emploi : explication, gravité, justification proposée, appliquée en "
     + "un clic, au besoin à tout le code"],
    [ic.book, COLOR.amber, "Voir la documentation",
     "Le manuel PDF de l'outil s'ouvre directement à la page du code"],
    [ic.code, COLOR.green, "Ouvrir le fichier source",
     "Le fichier cité s'affiche à la bonne ligne, ou dans votre éditeur"],
  ];
  helps.forEach(([img, color, head, text], i) => {
    const y = 1.6 + i * 1.7;
    addBadge(s, img, 0.6, y, 0.9, color, head);
    addTextBlock(s, 1.75, y, 4.0, 1.55, head, [text], `Aide ${head}`, { size: 14 });
  });
  addShot(s, "ia", { x: 6.1, y: 1.45, w: 6.6, h: 5.3 }, "Capture aide IA");
  s.addNotes("L'IA n'est pas imposée : le prompt s'affiche dans le terminal et dans une fenêtre ; "
             + "une IA se branche en implémentant une seule classe (AiProvider).");

  // 10 ── Didacticiel -----------------------------------------------------------------------
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Outils" });
  s.addText("Pris en main en cinq minutes", { placeholder: "title" });
  addShot(s, "didacticiel", { x: 0.6, y: 1.45, w: 8.1, h: 5.3 }, "Capture didacticiel");
  addBadge(s, ic.graduate, 9.1, 1.6, 0.8, COLOR.green, "Didacticiel");
  addTextBlock(s, 9.1, 2.6, 3.6, 4.2, "Didacticiel en 17 étapes",
               ["Proposé au premier lancement, puis Maj+F1",
                "L'élément expliqué est encadré à l'écran",
                "« Montre-moi » fait l'action à votre place sur un exemple réel"],
               "Texte didacticiel", { bullets: true, size: 15 });
  s.addNotes("Le contenu du didacticiel est un fichier texte modifiable sans toucher au code.");

  // 11 ── Sous le capot -------------------------------------------------------------------
  pres.addSection({ title: "Technique" });
  s = pres.addSlide({ masterName: "CONTENU", sectionTitle: "Technique" });
  s.addText("Sous le capot : une dette technique proche de zéro", { placeholder: "title" });
  const layers = [["Vue", "PyQt5, passive : affichage et signaux", COLOR.blue],
                  ["Présentateurs", "toute la logique d'interaction", COLOR.amber],
                  ["Modèle", "métier en Python pur, sans Qt", COLOR.green]];
  layers.forEach(([head, text, color], i) => {
    const y = 1.65 + i * 1.6;
    s.addShape("roundRect", { x: 0.6, y, w: 5.6, h: 1.3, rectRadius: 0.1, fill: { color },
                              line: { color }, objectName: `Couche ${head}` });
    s.addText([{ text: head, options: { bold: true, fontSize: 20, breakLine: true } },
               { text, options: { fontSize: 15 } }],
              { x: 0.85, y, w: 5.2, h: 1.3, fontFace: FONT, color: COLOR.white,
                valign: "middle", margin: 0, isTextBox: true, objectName: `Texte ${head}` });
  });
  const stats = [["64", "tests automatisés"], ["56", "modules documentés"],
                 ["4", "bibliothèques tierces"], ["6", "configurations testées en CI"]];
  stats.forEach(([value, label], i) => {
    const x = 6.85 + (i % 2) * 2.95;
    const y = 1.65 + Math.floor(i / 2) * 2.0;
    s.addText([{ text: value, options: { fontSize: 54, bold: true, color: COLOR.navy,
                                         breakLine: true } },
               { text: label, options: { fontSize: 14, color: COLOR.grey } }],
              { x, y, w: 2.75, h: 1.8, fontFace: FONT, margin: 0, valign: "top",
                isTextBox: true, objectName: `Chiffre ${label}` });
  });
  s.addText("PEP 8 · typage · docstrings partout · MVP vérifié par la CI · gestion de "
            + "configuration (SemVer, CHANGELOG, Git Flow)", {
    x: 6.85, y: 5.8, w: 5.85, h: 0.9, fontFace: FONT, fontSize: 13, italic: true,
    color: COLOR.grey, margin: 0, isTextBox: true, objectName: "Texte qualité" });
  s.addNotes("Détails complets dans docs/LogWaver_Documentation_Code.pdf : architecture, flux, "
             + "formats et référence de chaque classe et méthode.");

  // 12 ── Conclusion ----------------------------------------------------------------------
  s = pres.addSlide({ masterName: "TITRE_SOMBRE", sectionTitle: "Technique" });
  s.addText("Pour démarrer", { placeholder: "title" });
  s.addText([{ text: "pip install -r requirements.txt", options: { breakLine: true } },
             { text: "python main.py", options: { breakLine: true } },
             { text: "puis « Suivre le didacticiel »" }], { placeholder: "body" });
  s.addShape("roundRect", { x: 7.4, y: 1.9, w: 5.3, h: 3.9, rectRadius: 0.12,
                            fill: { color: COLOR.navy }, line: { color: COLOR.navy },
                            objectName: "Cadre ressources" });
  addBadge(s, ic.flask, 7.75, 2.2, 0.85, COLOR.green, "Ressources");
  s.addText([{ text: "Ressources", options: { bold: true, fontSize: 20, color: COLOR.white,
                                              breakLine: true, paraSpaceAfter: 6 } },
             { text: "github.com/DavidBoccara/LogWaver", options: { fontSize: 15,
                                                                    color: COLOR.ice,
                                                                    breakLine: true } },
             { text: "README.md : guide d'utilisation", options: { fontSize: 15,
                                                               color: COLOR.ice,
                                                               breakLine: true } },
             { text: "docs/LogWaver_Documentation_Code.pdf", options: { fontSize: 15,
                                                                     color: COLOR.ice,
                                                                     breakLine: true } },
             { text: "docs/GESTION_DE_CONFIGURATION.md", options: { fontSize: 15,
                                                                 color: COLOR.ice } }],
            { x: 7.75, y: 3.25, w: 4.75, h: 2.4, fontFace: FONT, valign: "top", margin: 0,
              isTextBox: true, objectName: "Texte ressources" });
  s.addNotes("Le dépôt contient le code, l'exemple TINTIN complet, la documentation et "
             + "l'historique de conception.");

  await pres.writeFile({ fileName: OUTPUT });
  console.log(`Présentation générée : ${OUTPUT}`);
}

build().catch((error) => { console.error(error); process.exit(1); });
