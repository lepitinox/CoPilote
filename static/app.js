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

async function api(methode, chemin, corps) {
  const r = await fetch("/api/" + chemin, {
    method: methode,
    headers: corps ? { "Content-Type": "application/json" } : {},
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
const ref = { lots: [] };
const classeLot = nom => { const i = ref.lots.indexOf(nom); return "lot-" + (i < 0 || i > 2 ? 3 : i); };
const pastilleLot = nom => (nom ? pastille(classeLot(nom), nom) : "—");
const nomsLots = () => (ref.lots.length ? ref.lots : ["V1"]);

// ---------- description des objets ----------
// champ : [clé, libellé, type, options, large] — options peut être une fonction.
const AXES = { contenu: "Livré dans ce lot", prerequis: "Prérequis", pour_qui: "Pour qui",
  comment: "Comment (canaux)", quoi: "Quoi (produits)", fonctionnalite: "Grâce à quelles fonctionnalités" };
const ENTITES = {
  jalon: { nom: "jalon", champs: [
    ["libelle", "Libellé", "texte", null, true], ["date", "Date", "date"],
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
    ["date", "Date de livraison", "date"], ["statut", "Statut", "choix", ["à venir", "en cours", "livré", "à arbitrer"]]] },
  lot_element: { nom: "élément de lot", champs: [
    ["lot", "Lot", "choix", nomsLots], ["axe", "Rubrique", "choix", Object.entries(AXES)],
    ["libelle", "Libellé", "texte", null, true], ["detail", "Précision", "texte", null, true]] },
  story: { nom: "story", champs: [
    ["etape", "Étape du parcours (colonne)", "texte"], ["rang_etape", "Ordre de l'étape", "nombre"],
    ["libelle", "Story", "texte", null, true], ["lot", "Lot", "choix", nomsLots],
    ["irritant", "Répond à un irritant", "case"], ["innovation", "Innovation", "case"]] },
  activite: { nom: "activité du planning", champs: [
    ["piste", "Piste (ligne du planning)", "texte"], ["libelle", "Activité", "texte"],
    ["debut", "Début", "date"], ["fin", "Fin", "date"]] },
  acteur: { nom: "acteur", champs: [
    ["nom", "Nom", "texte"], ["role", "Rôle", "texte"],
    ["cercle", "Cercle", "choix", ["équipe projet", "métier", "IT", "externe"]], ["entite", "Entité ou pôle", "texte"],
    ["adherence", "Adhérence avec l'équipe projet", "long", null, true]] },
  instance: { nom: "instance", champs: [
    ["nom", "Instance", "texte"], ["chantier", "Chantier", "texte"],
    ["objectifs", "Objectifs (un par ligne)", "long", null, true], ["participants", "Participants", "texte", null, true],
    ["frequence", "Fréquence", "texte"], ["duree", "Durée", "texte"], ["rang", "Ordre d'affichage", "nombre"]] },
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
    } else if (genre === "case") {
      s = el("input", { type: "checkbox", checked: !!v });
      saisies[cle] = [s, genre];
      return el("label", { class: "case" }, s, lib);
    } else if (genre === "long") {
      s = el("textarea", {}); s.value = v;
      if (cle === "texte") s.style.minHeight = "240px";
    } else {
      s = el("input", { type: genre === "date" ? "date" : genre === "nombre" ? "number" : "text", step: "any" });
      s.value = v;
    }
    saisies[cle] = [s, genre];
    return el("label", { class: large ? "large" : "" }, lib, s);
  });
  const form = el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    const corps = {};
    for (const [cle, [s, genre]] of Object.entries(saisies))
      corps[cle] = genre === "nombre" ? (s.value === "" ? null : Number(s.value)) : genre === "case" ? (s.checked ? 1 : 0) : s.value;
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
    el("span", { class: "pousse" }), actions),
  el("p", { class: "aide" }, aide)];

// ---------- navigation ----------
// VUES[clé] = [libellé du menu, groupe, fonction de rendu]
const VUES = {};
const GROUPES = ["Cadre de la mission", "Pilotage", "Saisie"];
const ORDRE = ["route", "lotissement", "storymap", "planning", "organisation", "gouvernance", "sprintkpi", "raci",
  "mission", "synthese", "kpi", "risques", "decisions", "meteo", "sprints", "cr"];
const etat = { vue: "route", cr: null, meteo: null, edition: false };

async function afficher(nom) {
  etat.vue = nom;
  try { history.replaceState(null, "", "#" + nom); } catch (e) { /* sans importance */ }
  for (const b of document.querySelectorAll("#menu button")) b.setAttribute("aria-current", b.dataset.vue === nom ? "page" : "false");
  const v = el("div", {});
  try {
    ref.lots = (await api("GET", "lot")).map(l => l.nom);
    await VUES[nom][2](v);
  } catch (e) { v.append(el("div", { class: "vide" }, e.message)); }
  if (etat.vue === nom) $("#vue").replaceChildren(v);
}
const recharger = () => afficher(etat.vue);

async function entete() {
  const [m, e] = await Promise.all([api("GET", "mission"), api("GET", "etat")]);
  $("#nom-mission").textContent = [m.nom, m.client].filter(Boolean).join(" — ");
  const l = $("#etat-llm");
  l.textContent = e.sdk_installe ? "Modèle : " + e.modele : "Modèle non installé";
  l.title = e.sdk_installe ? (e.cle_presente ? "Clé d'API détectée." : "Aucune clé d'API dans l'environnement : les fonctions de rédaction peuvent échouer.")
    : "Sans le paquet anthropic, l'extraction est indisponible et la météo est générée sans rédaction.";
  l.className = "pastille " + (e.sdk_installe && e.cle_presente ? "vert" : "orange");
}

function demarrer() {
  const menu = $("#menu");
  menu.append = ajouter;
  for (const g of GROUPES) {
    menu.append(el("h2", {}, g), ORDRE.filter(cle => VUES[cle] && VUES[cle][1] === g).map(cle => [cle, VUES[cle]]).map(([cle, v]) =>
      el("button", { "data-vue": cle, onclick: () => afficher(cle) }, v[0])));
  }
  $("#btn-demo").addEventListener("click", async e => {
    if (!confirm("Remplacer toutes les données par la mission de démonstration fictive ?")) return;
    await pendant(e.target, "Chargement…", async () => { await api("POST", "demo"); await entete(); await afficher("route"); dire("Mission de démonstration chargée."); });
  });
  const depart = location.hash.slice(1);
  entete().then(() => afficher(VUES[depart] ? depart : "route")).catch(e => dire(e.message, true));
}
