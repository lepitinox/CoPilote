"use strict";
// Socle de l'interface : utilitaires, formulaires, navigation.
// Les vues s'enregistrent dans VUES depuis cadre.js, pilotage.js et graphes.js.

const $ = (s, r = document) => r.querySelector(s);
const SVG = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, ...enfants) {
  const n = tag.startsWith("svg:") ? document.createElementNS(SVG, tag.slice(4)) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.setAttribute("class", v);
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  n.append = ajouter; n.replaceChildren = remplacer;
  n.append(enfants);
  return n;
}
// append et replaceChildren tolérants : tableaux imbriqués aplatis, valeurs vides ignorées.
const utiles = e => e.flat(Infinity).filter(x => x != null && x !== false);
function ajouter(...e) { Element.prototype.append.apply(this, utiles(e)); }
function remplacer(...e) { Element.prototype.replaceChildren.apply(this, utiles(e)); }

// Mission ouverte dans cet onglet : envoyée à chaque appel (deux onglets peuvent ouvrir deux missions).
const enTetesMission = () => (etat.mission ? { "X-Mission": etat.mission } : {});
async function api(methode, chemin, corps) {
  const r = await fetch("/api/" + chemin, {
    method: methode,
    headers: { ...enTetesMission(), ...(corps ? { "Content-Type": "application/json" } : {}) },
    body: corps ? JSON.stringify(corps) : undefined,
  });
  const d = await r.json().catch(() => ({ erreur: "Réponse illisible du serveur." }));
  if (!r.ok) throw new Error(d.erreur || "Erreur " + r.status);
  return d;
}

let minuterie;
function dire(texte, erreur = false) {
  const m = $("#message");
  m.textContent = texte; m.className = erreur ? "erreur" : ""; m.style.display = "block";
  clearTimeout(minuterie);
  minuterie = setTimeout(() => (m.style.display = "none"), erreur ? 9000 : 3500);
}
async function pendant(bouton, libelle, tache) {
  const avant = bouton.textContent;
  bouton.disabled = true; bouton.textContent = libelle;
  try { return await tache(); }
  catch (e) { dire(e.message, true); }
  finally { bouton.disabled = false; bouton.textContent = avant; }
}

const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
function dateFr(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? `${+m[3]} ${MOIS[+m[2] - 1]} ${m[1]}` : "—";
}
const jour = iso => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || ""); return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null; };
const nb = v => (v == null || v === "" ? "—" : Number(v).toLocaleString("fr-FR"));
const pct = v => (v == null ? "—" : Math.round(v * 100) + " %");
const LIB_TENDANCE = { vert: "Vert", orange: "Orange", rouge: "Rouge" };
const pastille = (classe, texte) => el("span", { class: "pastille " + classe }, texte);
const tendance = t => (t ? pastille(t, LIB_TENDANCE[t] || t) : "—");
const tuile = (nom, valeur, note) => el("div", { class: "carte tuile" },
  el("div", { class: "nom" }, nom), el("div", { class: "valeur" }, valeur), note && el("div", { class: "note" }, note));

// Références partagées entre vues (noms des lots pour les listes et les couleurs).
const ref = { lots: [], acteurs: [], metiers: [], profils: [], jalons: [], recurrences: {}, exports: null };
const nomsMetiers = () => [["", "—"], ...ref.metiers.map(m => [m.nom, m.nom])];
const acteurParId = id => ref.acteurs.find(a => a.id === Number(id));
const idsDe = v => { try { const l = JSON.parse(v || "[]"); return Array.isArray(l) ? l.map(Number) : []; } catch (e) { return []; } };
const classeLot = nom => { const i = ref.lots.indexOf(nom); return "lot-" + (i < 0 || i > 2 ? 3 : i); };
const pastilleLot = nom => (nom ? pastille(classeLot(nom), nom) : "—");
const nomsLots = () => (ref.lots.length ? ref.lots : ["V1"]);

// ---------- description des objets ----------
// champ : [clé, libellé, type, options, large] — options peut être une fonction.
const AXES = { contenu: "Livré dans ce lot", prerequis: "Prérequis", pour_qui: "Pour qui",
  comment: "Comment (canaux)", quoi: "Quoi (produits)", fonctionnalite: "Grâce à quelles fonctionnalités" };
const ENTITES = {
  jalon: { nom: "jalon", champs: [
    ["libelle", "Libellé", "texte", null, true], ["date", "Date prévue", "date"],
    ["date_initiale", "Date de référence (engagement) — à changer seulement après un avenant", "date"],
    ["version", "Lot", "choix", nomsLots], ["statut", "Statut", "choix", ["à venir", "atteint", "en retard"]]] },
  livrable: { nom: "livrable", champs: [
    ["chantier", "Chantier", "texte"], ["libelle", "Livrable", "texte"],
    ["avancement", "Avancement (%)", "nombre"], ["tendance", "Tendance", "choix", ["vert", "orange", "rouge"]],
    ["statut", "Statut en une ligne", "texte", null, true]] },
  sprint: { nom: "sprint", champs: [
    ["numero", "Numéro", "nombre"], ["date_fin", "Date de fin", "date"],
    ["capacite", "Capacité (j/h)", "nombre"], ["prevu", "Points prévus", "nombre"],
    ["realise", "Points réalisés", "nombre"], ["ajoute", "Points ajoutés au backlog", "nombre"],
    ["reste", "Reste à faire en fin de sprint", "nombre"], ["moral", "Moral (1 à 5)", "nombre"],
    ["anomalies_creees", "Anomalies créées", "nombre"], ["anomalies_corrigees", "Anomalies corrigées", "nombre"]] },
  risque: { nom: "risque ou adhérence", champs: [
    ["nature", "Nature", "choix", ["risque", "adherence"]], ["etat", "État", "choix", ["ouvert", "en traitement", "clos"]],
    ["titre", "Titre", "texte", null, true], ["description", "Description (cause, conséquence)", "long", null, true],
    ["probabilite", "Probabilité (1 à 3)", "nombre"], ["impact", "Impact (1 à 3)", "nombre"],
    ["evolution", "Évolution (saisie)", "choix", ["hausse", "stable", "baisse"]], ["lot", "Lot impacté", "texte"],
    ["porteur", "Porteur", "texte"], ["echeance", "Échéance", "date"],
    ["plan_action", "Plan d'action", "long", null, true], ["maj_le", "Dernière mise à jour", "date"]] },
  decision: { nom: "décision ou action", champs: [
    ["nature", "Nature", "choix", ["decision", "action"]],
    ["statut", "Statut", "choix", ["à prendre", "prise", "à faire", "faite"]],
    ["titre", "Titre", "texte", null, true], ["detail", "Détail", "long", null, true],
    ["porteur", "Décideur ou porteur", "texte"], ["echeance", "Échéance", "date"],
    ["instance", "Instance", "texte"]] },
  compte_rendu: { nom: "compte rendu", champs: [
    ["date", "Date", "date"], ["titre", "Titre", "texte"],
    ["texte", "Texte du compte rendu ou des notes", "long", null, true]] },
  lot: { nom: "lot", champs: [
    ["nom", "Nom court (V1, V2…)", "texte"], ["rang", "Ordre d'affichage", "nombre"],
    ["titre", "Titre", "texte", null, true], ["periode", "Période affichée (ex. Mars 2027, T2 2027)", "texte"],
    ["date", "Date de livraison prévue", "date"], ["date_initiale", "Date de référence (engagement)", "date"],
    ["statut", "Statut", "choix", ["à venir", "en cours", "livré", "à arbitrer"]]] },
  lot_element: { nom: "élément de lot", champs: [
    ["lot", "Lot", "choix", nomsLots], ["axe", "Rubrique", "choix", Object.entries(AXES)],
    ["libelle", "Libellé", "texte", null, true], ["detail", "Précision", "texte", null, true],
    ["statut", "État (prérequis)", "choix", ["", "obtenu", "en attente", "bloquant"]]] },
  story: { nom: "story", champs: [
    ["etape", "Étape du parcours (colonne)", "texte"], ["rang_etape", "Ordre de l'étape", "nombre"],
    ["libelle", "Story", "texte", null, true], ["lot", "Lot", "choix", nomsLots],
    ["irritant", "Répond à un irritant", "case"], ["innovation", "Innovation", "case"]] },
  activite: { nom: "activité du planning", champs: [
    ["piste", "Piste (ligne du planning)", "texte"], ["libelle", "Activité", "texte"],
    ["debut", "Début", "date"], ["fin", "Fin", "date"]] },
  metier: { nom: "métier", champs: [["nom", "Métier", "texte"], ["rang", "Ordre d'affichage", "nombre"]] },
  acteur: { nom: "acteur", champs: [
    ["nom", "Nom", "texte"], ["role", "Rôle", "texte"],
    ["metier", "Métier", "choix", nomsMetiers], ["email", "E-mail (pour les invitations)", "texte"],
    ["cercle", "Cercle", "choix", ["équipe projet", "métier", "IT", "externe"]], ["entite", "Entité ou pôle", "texte"],
    ["adherence", "Adhérence avec l'équipe projet", "long", null, true]] },
  instance: { nom: "instance", champs: [
    ["nom", "Instance", "texte"], ["chantier", "Chantier", "texte"],
    ["objectifs", "Objectifs (un par ligne)", "long", null, true],
    ["participants_ids", "Participants (personnes de l'organisation)", "personnes", null, true],
    ["participants", "Autres participants (texte libre)", "texte", null, true],
    ["recurrence", "Récurrence", "choix", () => [["", "—"], ...Object.entries(ref.recurrences)]],
    ["frequence", "Fréquence (libellé affiché)", "texte"],
    ["premiere", "Première séance", "date"], ["heure", "Heure", "heure"],
    ["duree_min", "Durée (minutes)", "nombre"], ["duree", "Durée (libellé affiché)", "texte"],
    ["rang", "Ordre d'affichage", "nombre"]] },
  estimation: { nom: "élément chiffré", champs: [
    ["mode", "Mode", "choix", [["macro", "Macro (peu d'informations)"], ["detaille", "Détaillé (après collecte)"]]],
    ["lot", "Lot", "choix", () => [["", "—"], ...nomsLots().map(n => [n, n])]],
    ["libelle", "Élément", "texte", null, true],
    ["taille", "Taille (macro)", "choix", ["", "XS", "S", "M", "L", "XL"]],
    ["confiance", "Confiance (macro)", "choix", ["", "forte", "moyenne", "faible"]],
    ["profil", "Profil (détaillé)", "choix", () => [["", "—"], ...ref.profils.map(p => [p.nom, p.nom])]],
    ["jours_bas", "Jours — bas", "nombre"], ["jours_probable", "Jours — probable (macro : remplace l'abaque)", "nombre"],
    ["jours_haut", "Jours — haut", "nombre"], ["rang", "Ordre d'affichage", "nombre"],
    ["hypothese", "Hypothèses", "long", null, true]] },
  profil: { nom: "profil", champs: [
    ["nom", "Profil", "texte"], ["metier", "Métier", "choix", nomsMetiers],
    ["tjm", "TJM de vente (€)", "nombre"], ["cout_journalier", "Coût journalier (€)", "nombre"],
    ["raf_jours", "Reste à faire (jours)", "nombre"], ["rang", "Ordre d'affichage", "nombre"]] },
  consommation: { nom: "consommation", champs: [
    ["mois", "Mois (AAAA-MM)", "texte"], ["profil", "Profil", "choix", () => [["", "—"], ...ref.profils.map(p => [p.nom, p.nom])]],
    ["jours", "Jours consommés", "nombre"], ["commentaire", "Commentaire", "texte", null, true]] },
  depense: { nom: "dépense", champs: [
    ["libelle", "Dépense", "texte", null, true], ["date", "Date", "date"],
    ["categorie", "Catégorie", "choix", ["", "logiciel", "matériel", "déplacement", "sous-traitance", "autre"]],
    ["montant", "Montant (€)", "nombre"], ["statut", "Statut", "choix", ["prévue", "engagée", "payée"]]] },
  facture: { nom: "échéance de facturation", champs: [
    ["libelle", "Échéance", "texte", null, true], ["date_prevue", "Date prévue", "date"],
    ["montant", "Montant (€)", "nombre"], ["statut", "Statut", "choix", ["à facturer", "facturée", "payée"]],
    ["jalon", "Jalon déclencheur", "choix", () => [["", "—"], ...ref.jalons.map(j => [j.libelle, j.libelle])]]] },
  attente: { nom: "attente du client", champs: [
    ["partie_prenante", "Partie prenante", "choix", () => [["", "—"], ...ref.acteurs.map(a => [a.nom, a.nom])]],
    ["categorie", "Catégorie", "choix", ["", "délai", "périmètre", "qualité", "coût", "relation", "communication"]],
    ["libelle", "Attente exprimée", "texte", null, true],
    ["priorite", "Priorité (1 : forte, 3 : faible)", "nombre"], ["satisfaction", "Satisfaction perçue (1 à 5)", "nombre"],
    ["position", "Position", "choix", ["alignée", "à recadrer", "hors périmètre"]], ["echeance", "Échéance", "date"],
    ["reponse", "Notre réponse, engagement ou message de recadrage", "long", null, true],
    ["prochaine_action", "Prochaine action", "texte", null, true], ["revue_le", "Dernière revue avec le client", "date"]] },
  changement: { nom: "demande de changement", champs: [
    ["titre", "Demande", "texte", null, true], ["description", "Ce qui est demandé, et pourquoi", "long", null, true],
    ["demandeur", "Demandeur", "choix", () => [["", "—"], ...ref.acteurs.map(a => [a.nom, a.nom])]],
    ["decideur", "Qui décide", "choix", () => [["", "—"], ...ref.acteurs.map(a => [a.nom, a.nom])]],
    ["lot", "Lot concerné", "choix", () => [["", "—"], ...nomsLots().map(n => [n, n])]],
    ["origine_type", "Origine", "choix", [["directe", "Demande directe"], ["attente", "Attente du client"], ["hypothese", "Hypothèse invalidée"], ["risque", "Risque"]]],
    ["impact_delai_jours", "Décalage des jalons si acceptée (jours)", "nombre"],
    ["jalons_ids", "Jalons décalés si la demande est acceptée", "jalons", null, true],
    ["statut", "Statut", "choix", ["à instruire", "chiffrée", "présentée", "acceptée", "refusée", "reportée"]]] },
  hypothese: { nom: "hypothèse", champs: [
    ["libelle", "Hypothèse", "texte", null, true],
    ["categorie", "Catégorie", "choix", ["planning", "chiffrage", "périmètre", "organisation", "technique", "données", "budget"]],
    ["statut", "Statut", "choix", ["à vérifier", "confirmée", "invalidée"]],
    ["porteur", "Qui doit la confirmer", "choix", () => [["", "—"], ...ref.acteurs.map(a => [a.nom, a.nom])]],
    ["echeance", "À vérifier avant le", "date"], ["lot", "Lot concerné", "choix", () => [["", "—"], ...nomsLots().map(n => [n, n])]],
    ["source", "Source (atelier, contrat, comité…)", "texte"],
    ["impact", "Conséquence si elle est invalidée (reprise dans le risque créé)", "long", null, true]] },
  raci: { nom: "activité du RACI", champs: [
    ["domaine", "Domaine", "texte"], ["rang", "Ordre d'affichage", "nombre"],
    ["activite", "Activité", "texte", null, true]] },
};

function formulaire(type, objet, apres, defauts = {}) {
  const def = ENTITES[type], d = $("#dialogue"), saisies = {};
  const champs = def.champs.map(([cle, lib, genre, options, large]) => {
    let s;
    const v = objet?.[cle] ?? defauts[cle] ?? "";
    if (genre === "choix") {
      const liste = (typeof options === "function" ? options() : options).map(o => (Array.isArray(o) ? o : [o, o]));
      if (v !== "" && !liste.some(o => o[0] === v)) liste.push([v, v]);
      s = el("select", {}, liste.map(([val, texte]) => el("option", { value: val, selected: val === v }, texte)));
    } else if (genre === "personnes") {
      const choisis = new Set(idsDe(v));
      const cases = ref.acteurs.map(a => el("label", { class: "case", style: "font-size:14px" },
        el("input", { type: "checkbox", value: a.id, checked: choisis.has(a.id) }),
        a.nom, el("span", { style: "color:var(--doux)" }, " · " + (a.metier || a.role || ""))));
      s = el("div", { class: "personnes" }, cases.length ? cases : el("span", { style: "color:var(--doux)" }, "Aucune personne dans l'organisation."));
      saisies[cle] = [s, genre];
      return el("div", { class: large ? "large" : "" }, el("div", { style: "font-size:13px;color:var(--doux);margin-bottom:4px" }, lib), s);
    } else if (genre === "jalons") {
      const choisis = new Set(idsDe(v));
      const cases = ref.jalons.map(j => el("label", { class: "case", style: "font-size:14px" },
        el("input", { type: "checkbox", value: j.id, checked: choisis.has(j.id) }),
        j.libelle, el("span", { style: "color:var(--doux)" }, " · " + dateFr(j.date))));
      s = el("div", { class: "personnes" }, cases.length ? cases : el("span", { style: "color:var(--doux)" }, "Aucun jalon."));
      saisies[cle] = [s, "personnes"];
      return el("div", { class: large ? "large" : "" }, el("div", { style: "font-size:13px;color:var(--doux);margin-bottom:4px" }, lib), s);
    } else if (genre === "case") {
      s = el("input", { type: "checkbox", checked: !!v });
      saisies[cle] = [s, genre];
      return el("label", { class: "case" }, s, lib);
    } else if (genre === "long") {
      s = el("textarea", {}); s.value = v;
      if (cle === "texte") s.style.minHeight = "240px";
    } else {
      s = el("input", { type: { date: "date", nombre: "number", heure: "time" }[genre] || "text", step: genre === "heure" ? 300 : "any" });
      s.value = v;
    }
    saisies[cle] = [s, genre];
    return el("label", { class: large ? "large" : "" }, lib, s);
  });
  const form = el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    const corps = {};
    for (const [cle, [s, genre]] of Object.entries(saisies))
      corps[cle] = genre === "nombre" ? (s.value === "" ? null : Number(s.value)) : genre === "case" ? (s.checked ? 1 : 0)
        : genre === "personnes" ? JSON.stringify([...s.querySelectorAll("input:checked")].map(c => Number(c.value))) : s.value;
    // À la création, les valeurs par défaut hors formulaire (origine, rattachement) sont transmises.
    if (!objet) for (const [k, val] of Object.entries(defauts)) if (!(k in corps)) corps[k] = val;
    try {
      if (objet) await api("PUT", `${type}/${objet.id}`, corps); else await api("POST", type, corps);
      d.close(); await apres();
    } catch (err) { dire(err.message, true); }
  } },
    el("h3", {}, (objet ? "Modifier : " : "Ajouter : ") + def.nom),
    el("div", { class: "champs" }, champs),
    el("div", { class: "barre" },
      objet && el("button", { type: "button", class: "danger", onclick: async () => {
        if (!confirm("Supprimer définitivement cet élément ?")) return;
        try { await api("DELETE", `${type}/${objet.id}`); d.close(); await apres(); }
        catch (err) { dire(err.message, true); }
      } }, "Supprimer"),
      el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Annuler"),
      el("button", { class: "principal" }, "Enregistrer")));
  d.replaceChildren(form); d.showModal();
}

function tableau(type, lignes, colonnes, apres) {
  if (!lignes.length) return el("div", { class: "vide" }, "Aucun élément pour l'instant.");
  return el("div", { class: "cadre-table" }, el("table", {},
    el("thead", {}, el("tr", {}, colonnes.map(c => el("th", {}, c[0])))),
    el("tbody", {}, lignes.map(l => el("tr", {
      class: "cliquable", tabindex: 0, title: "Modifier",
      onclick: () => formulaire(type, l, apres),
      onkeydown: e => { if (e.key === "Enter") formulaire(type, l, apres); },
    }, colonnes.map(c => el("td", { class: c[2] || "" }, c[1](l))))))));
}
function section(titre, type, lignes, colonnes, apres) {
  return el("section", {}, el("div", { class: "barre", style: "margin-top:20px" }, el("h3", { style: "margin:0" }, titre),
    el("button", { class: "pousse", onclick: () => formulaire(type, null, apres) }, "Ajouter")),
    tableau(type, lignes, colonnes, apres));
}
const titreVue = (titre, aide, ...actions) => [
  el("div", { class: "barre", style: "margin-top:0" }, el("h2", { style: "margin:0;font-size:20px" }, titre),
    el("span", { class: "pousse" }), actions, boutonsExport(etat.exportVue || etat.vue)),
  el("p", { class: "aide" }, aide)];

// ---------- exports PowerPoint / Excel ----------
async function telechargerFichier(url, bouton) {
  const tache = async () => {
    const r = await fetch(url, { headers: enTetesMission() });
    if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.erreur || "Erreur " + r.status); }
    const nom = decodeURIComponent((/filename\*=UTF-8''([^;]+)/.exec(r.headers.get("Content-Disposition") || "") || [])[1] || "export");
    const a = el("a", { href: URL.createObjectURL(await r.blob()), download: nom });
    document.body.append(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  };
  if (bouton) return pendant(bouton, "…", tache);
  try { await tache(); } catch (e) { dire(e.message, true); }
}
function boutonsExport(vue) {
  const ex = ref.exports;
  if (!ex || !ex.libelles[vue]) return null;
  const extra = vue === "meteo" && etat.meteo ? "?meteo=" + etat.meteo : "";
  return el("span", { class: "exports" },
    el("button", { title: "Exporter cette vue en PowerPoint", onclick: e => telechargerFichier(`/api/export/${vue}.pptx${extra}`, e.target) }, "PowerPoint"),
    !ex.sans_excel.includes(vue) && el("button", { title: "Exporter cette vue en Excel", onclick: e => telechargerFichier(`/api/export/${vue}.xlsx`, e.target) }, "Excel"),
    el("button", { title: "Modèles d'export de cette vue", onclick: () => dialogueModeles(vue) }, "Modèles"));
}
function dialogueModeles(vue) {
  const d = $("#dialogue"), ex = ref.exports;
  const source = ext => (ex.vues[vue]?.[ext] ? "propre à cette vue" : ex.commun[ext] ? "modèle commun" : "modèle par défaut");
  const envoyer = (cible, ext) => {
    const choix = el("input", { type: "file", accept: "." + ext, style: "display:none" });
    choix.addEventListener("change", async () => {
      const f = choix.files[0]; if (!f) return;
      try {
        const r = await fetch(`/api/modele/${cible}.${ext}`, { method: "PUT", headers: { "Content-Type": "application/octet-stream" }, body: f });
        const res = await r.json(); if (!r.ok) throw new Error(res.erreur);
        Object.assign(ex, res); dire("Modèle enregistré."); dialogueModeles(vue);
      } catch (e) { dire(e.message, true); }
    });
    document.body.append(choix); choix.click(); setTimeout(() => choix.remove(), 60000);
  };
  const retirer = async (cible, ext) => {
    try { Object.assign(ex, await api("DELETE", `modele/${cible}.${ext}`)); dire("Modèle retiré."); dialogueModeles(vue); }
    catch (e) { dire(e.message, true); }
  };
  const bloc = (ext, libelle) => el("div", { class: "carte", style: "display:grid;gap:8px" },
    el("div", {}, el("b", {}, libelle), " — utilisé actuellement : ", pastille("neutre", source(ext))),
    el("div", { class: "barre", style: "margin:0" },
      el("button", { onclick: e => telechargerFichier(`/api/modele/${vue}.${ext}`, e.target) }, "Télécharger le modèle"),
      el("button", { onclick: () => envoyer(vue, ext) }, "Remplacer pour cette vue"),
      el("button", { onclick: () => envoyer("commun", ext) }, "Remplacer pour toutes les vues")),
    (ex.vues[vue]?.[ext] || ex.commun[ext]) && el("div", { class: "barre", style: "margin:0" },
      ex.vues[vue]?.[ext] && el("button", { class: "danger", onclick: () => retirer(vue, ext) }, "Retirer le modèle de cette vue"),
      ex.commun[ext] && el("button", { class: "danger", onclick: () => retirer("commun", ext) }, "Retirer le modèle commun")));
  d.replaceChildren(el("form", { method: "dialog" },
    el("h3", {}, "Modèles d'export — " + ex.libelles[vue]),
    el("p", { class: "aide", style: "margin:0" },
      "Téléchargez le modèle, modifiez-le dans PowerPoint ou Excel, puis renvoyez-le. Jetons remplacés à l'export : {{titre}}, {{mission}}, {{date}}."),
    el("ul", { class: "aide", style: "margin:0;padding-left:18px" },
      el("li", {}, "PowerPoint : le masque des diapositives donne les couleurs, polices, logo et pied de page ; les diapositives présentes dans le modèle (page de garde) sont conservées."),
      el("li", {}, "Excel : la première feuille sert de gabarit pour chaque onglet ; la cellule {{contenu}} indique où écrire et donne le style des en-têtes, la cellule au-dessous celui des lignes.")),
    bloc("pptx", "PowerPoint"),
    !ex.sans_excel.includes(vue) && bloc("xlsx", "Excel"),
    el("div", { class: "barre" }, el("span", { class: "pousse" }), el("button", { class: "principal" }, "Fermer"))));
  if (!d.open) d.showModal();
}

// ---------- navigation ----------
// VUES[clé] = [libellé du menu, groupe, fonction de rendu]
const VUES = {};
// Menu rangé par moment du pilotage : ce que je fais aujourd'hui, je pilote, je prépare et rends
// compte, je cadre, je saisis.
const MENU = [
  ["Aujourd'hui", ["aujourdhui", "synthese"]],
  ["Piloter", ["risques", "attentes", "decisions", "changements", "planning", "kpi", "budget"]],
  ["Préparer et rendre compte", ["gouvernance", "meteo"]],
  ["Cadrer", ["mission", "route", "storymap", "organisation", "raci", "chiffrage"]],
  ["Saisir", ["sprints", "budget_saisie", "cr", "historique"]],
];
const GROUPES = ["Aujourd'hui", "Cadre de la mission", "Pilotage", "Finances", "Saisie"];
const ORDRE = ["aujourdhui", "route", "lotissement", "storymap", "planning", "organisation", "gouvernance", "sprintkpi", "raci",
  "mission", "synthese", "kpi", "risques", "attentes", "decisions", "meteo", "chiffrage", "budget", "sprints", "cr", "historique"];
const etat = { vue: "aujourdhui", cr: null, meteo: null, edition: false, mission: null, missions: [] };

async function afficher(nom) {
  etat.vue = nom; etat.exportVue = null;
  try { history.replaceState(null, "", "#" + nom); } catch (e) { /* sans importance */ }
  for (const b of document.querySelectorAll("#menu button")) b.setAttribute("aria-current", b.dataset.vue === nom ? "page" : "false");
  const v = el("div", {});
  try {
    const [lots, acteurs, metiers, profils, jalons] = await Promise.all(["lot", "acteur", "metier", "profil", "jalon"].map(t => api("GET", t)));
    ref.lots = lots.map(l => l.nom); ref.acteurs = acteurs; ref.metiers = metiers; ref.profils = profils; ref.jalons = jalons;
    if (!ref.exports) {
      const [ex, ag] = await Promise.all([api("GET", "modeles"), api("GET", "agenda")]);
      ref.exports = ex; ref.recurrences = ag.recurrences;
    }
    await VUES[nom][2](v);
  } catch (e) { v.append(el("div", { class: "vide" }, e.message)); }
  if (etat.vue === nom) $("#vue").replaceChildren(v);
}
const recharger = () => afficher(etat.vue);

async function entete() {
  const [m, e] = await Promise.all([api("GET", "mission"), api("GET", "etat")]);
  $("#nom-mission").textContent = [m.nom, m.client].filter(Boolean).join(" — ");
  const fiche = etat.missions.find(x => x.cle === etat.mission);
  if (fiche && (fiche.nom !== m.nom || fiche.client !== (m.client || ""))) {
    Object.assign(fiche, { nom: m.nom, client: m.client || "" }); remplirChoixMission();
  }
  const l = $("#etat-llm");
  l.textContent = e.sdk_installe ? "Modèle : " + e.modele : "Modèle non installé";
  l.title = e.sdk_installe ? (e.cle_presente ? "Clé d'API détectée." : "Aucune clé d'API dans l'environnement : les fonctions de rédaction peuvent échouer.")
    : "Sans le paquet anthropic, l'extraction est indisponible et la météo est générée sans rédaction.";
  l.className = "pastille " + (e.sdk_installe && e.cle_presente ? "vert" : "orange");
}

// ---------- missions : choix, création, import, export, corbeille ----------
const MEMO_MISSION = "copilote.mission";
function memoriser(cle) { try { localStorage.setItem(MEMO_MISSION, cle); } catch (e) { /* sans importance */ } }
async function listerMissions() {
  const r = await api("GET", "missions");
  etat.missions = r.missions; etat.reprises = r.reprises;
  return r;
}
function remplirChoixMission() {
  const s = $("#choix-mission");
  s.replaceChildren(...etat.missions.map(m => el("option", { value: m.cle, selected: m.cle === etat.mission },
    m.nom + (m.client ? " — " + m.client : ""))), el("option", { value: "+nouvelle" }, "+ Nouvelle mission…"));
}

// Création guidée : la fiche de départ et, au besoin, le cadre repris d'une mission existante.
function dialogueNouvelleMission() {
  const d = $("#dialogue");
  const champ = (cle, lib, type = "text", attrs = {}) => {
    const i = el(type === "long" ? "textarea" : "input", { name: cle, type: type === "long" ? null : type, ...attrs });
    return [el("label", { class: type === "long" ? "large" : "" }, lib, i), i];
  };
  const [lNom, nom] = champ("nom", "Nom de la mission *", "text", { required: true });
  const [lClient, client] = champ("client", "Client");
  const [lCible, cible] = champ("date_cible", "Date cible", "date");
  const [lBudget, budget] = champ("budget_vendu", "Budget vendu (€, facultatif)", "number", { step: "any" });
  const [lObjB, objB] = champ("objectif_business", "Objectif business (ce que le client veut obtenir)", "long");
  const [lObjP, objP] = champ("objectif_projet", "Objectif projet (date, périmètre, budget)", "long");
  const [lPilote, pilote] = champ("porteur_projet", "Porteur projet (pilote)");
  const [lSprint, sprint] = champ("duree_sprint_jours", "Durée d'un sprint (jours, si agile)", "number", { min: 1 });
  sprint.value = 14;
  const source = el("select", {}, el("option", { value: "" }, "Partir de zéro"),
    etat.missions.map(m => el("option", { value: m.cle, selected: m.cle === etat.mission && m.cle !== "demo" }, "Reprendre le cadre de : " + m.nom)));
  const cases = Object.entries(etat.reprises || {}).map(([cle, lib]) =>
    el("label", { class: "case", style: "font-size:14px" }, el("input", { type: "checkbox", value: cle, checked: cle !== "raci" }), lib));
  const zoneReprise = el("div", { class: "personnes", style: "max-height:none" }, cases);
  const majReprise = () => { zoneReprise.style.display = source.value ? "" : "none"; };
  source.addEventListener("change", majReprise);
  d.replaceChildren(el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    if (!nom.value.trim()) { nom.focus(); return; }
    const fiche = { nom: nom.value, client: client.value, date_cible: cible.value, objectif_business: objB.value,
      objectif_projet: objP.value, porteur_projet: pilote.value, duree_sprint_jours: Number(sprint.value) || 14 };
    if (budget.value !== "") fiche.budget_vendu = Number(budget.value);
    const reprendre = source.value ? [...zoneReprise.querySelectorAll("input:checked")].map(c => c.value) : [];
    try {
      const r = await api("POST", "missions", { fiche, source: source.value || null, reprendre });
      await listerMissions(); d.close(); await ouvrirMission(r.cle, "aujourdhui");
      dire("Mission créée : suivez les étapes de démarrage.");
    } catch (err) { dire(err.message, true); }
  } },
    el("h3", {}, "Nouvelle mission"),
    el("p", { class: "aide", style: "margin:0" }, "Le minimum pour démarrer ; le reste se complète ensuite, guidé par la liste « Démarrage de la mission » de la page À traiter."),
    el("div", { class: "champs" }, lNom, lClient, lCible, lBudget, lObjB, lObjP, lPilote, lSprint),
    el("label", {}, "Point de départ", source), zoneReprise,
    el("p", { class: "aide", style: "margin:0" }, "Seul le cadre est repris (personnes, réunions, tarifs, responsabilités, paramètres) : aucun risque, jalon, chiffrage ni donnée de suivi."),
    el("div", { class: "barre" }, el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Annuler"), el("button", { class: "principal" }, "Créer la mission"))));
  majReprise();
  d.showModal(); nom.focus();
}
async function ouvrirMission(cle, vue) {
  etat.mission = cle; etat.cr = null; etat.meteo = null; memoriser(cle);
  await api("PUT", `missions/${cle}/ouvrir`).catch(() => null);
  remplirChoixMission();
  await entete();
  await afficher(vue || etat.vue);
}
function dialogueMissions() {
  const d = $("#dialogue");
  const rafraichir = async () => { await listerMissions(); remplirChoixMission(); dialogueMissions(); };
  const importer = () => {
    const choix = el("input", { type: "file", accept: ".json,application/json", style: "display:none" });
    choix.addEventListener("change", async () => {
      const f = choix.files[0]; if (!f) return;
      try {
        let contenu;
        try { contenu = JSON.parse(await f.text()); } catch (e) { throw new Error("Ce fichier n'est pas un JSON lisible."); }
        const r = await api("POST", "missions/importer", { fichier: contenu });
        await listerMissions(); d.close(); await ouvrirMission(r.cle, "route");
        dire("Mission importée." + (r.avertissements.length ? " " + r.avertissements.join(" ") : ""));
      } catch (e) { dire(e.message, true); }
    });
    document.body.append(choix); choix.click(); setTimeout(() => choix.remove(), 60000);
  };
  const lignes = etat.missions.map(m => el("tr", {},
    el("td", {}, el("b", {}, m.nom), m.client && el("div", { style: "color:var(--doux);font-size:13px" }, m.client),
      m.cle === etat.mission && pastille("vert", "ouverte")),
    el("td", { style: "white-space:nowrap;color:var(--doux);font-size:13px" }, dateFr(m.modifiee_le) + " " + (m.modifiee_le || "").slice(11, 16)),
    el("td", { style: "white-space:nowrap" },
      m.cle !== etat.mission && el("button", { type: "button", onclick: async () => { d.close(); await ouvrirMission(m.cle); } }, "Ouvrir"), " ",
      el("button", { type: "button", title: "Télécharger la mission en un fichier JSON", onclick: e => telechargerFichier(`/api/missions/${m.cle}/export`, e.target) }, "Exporter"), " ",
      el("button", { type: "button", class: "danger", onclick: async () => {
        if (!confirm(`Mettre la mission « ${m.nom} » à la corbeille ?\nLe fichier est déplacé dans missions/corbeille et peut y être récupéré.`)) return;
        try {
          const r = await api("DELETE", `missions/${m.cle}`);
          etat.missions = r.missions;
          if (m.cle === etat.mission) { d.close(); await ouvrirMission(r.derniere); } else await rafraichir();
          dire("Mission mise à la corbeille.");
        } catch (e) { dire(e.message, true); }
      } }, "Corbeille"))));
  d.replaceChildren(el("form", { method: "dialog", onsubmit: e => { e.preventDefault(); dialogueNouvelleMission(); } },
    el("h3", {}, "Missions"),
    el("p", { class: "aide", style: "margin:0" }, "Chaque mission est un fichier séparé. L'export produit un fichier JSON lisible (données et historique) qui se réimporte ici, comme nouvelle mission."),
    el("div", { class: "cadre-table" }, el("table", {}, el("tbody", {}, lignes))),
    el("div", { class: "barre" },
      el("button", { class: "principal" }, "Nouvelle mission…"),
      el("button", { type: "button", onclick: importer }, "Importer un fichier…"),
      el("button", { type: "button", title: "Mission fictive, dans sa propre mission « demo »", onclick: async e => {
        if (etat.missions.some(m => m.cle === "demo") && !confirm("Réinitialiser la mission de démonstration ?")) return;
        await pendant(e.target, "Chargement…", async () => {
          const r = await api("POST", "demo"); await listerMissions(); d.close(); await ouvrirMission(r.cle, "route");
          dire("Mission de démonstration chargée.");
        });
      } }, "Charger la démo"),
      el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Fermer"))));
  if (!d.open) d.showModal();
}

async function demarrer() {
  const menu = $("#menu");
  menu.append = ajouter;
  for (const [g, cles] of MENU) {
    menu.append(el("h2", {}, g), cles.filter(cle => VUES[cle]).map(cle =>
      el("button", { "data-vue": cle, onclick: () => afficher(cle) }, VUES[cle][0])));
  }
  $("#btn-missions").addEventListener("click", dialogueMissions);
  $("#btn-nouvelle").addEventListener("click", dialogueNouvelleMission);
  $("#choix-mission").addEventListener("change", e => {
    if (e.target.value === "+nouvelle") { remplirChoixMission(); dialogueNouvelleMission(); return; }
    ouvrirMission(e.target.value);
  });
  const depart = location.hash.slice(1);
  try {
    const r = await listerMissions();
    let memo = null; try { memo = localStorage.getItem(MEMO_MISSION); } catch (e) { /* sans importance */ }
    etat.mission = etat.missions.some(m => m.cle === memo) ? memo : r.derniere;
    remplirChoixMission();
    await entete();
    await afficher(VUES[depart] ? depart : "aujourdhui");
  } catch (e) { dire(e.message, true); }
}
