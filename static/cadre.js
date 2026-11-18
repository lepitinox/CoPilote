"use strict";
// Vues du cadre de la mission : feuille de route, lotissement, story map, macro-planning,
// organisation, gouvernance, rappel du sprint, RACI, fiche mission.
const CADRE = "Cadre de la mission";

const STATUTS_HYP = { "à vérifier": "orange", "confirmée": "vert", "invalidée": "rouge" };
const pastilleHypothese = st => pastille(STATUTS_HYP[st] || "neutre", st || "à vérifier");
const colonnesHypotheses = [
  ["Hypothèse", h => [el("b", {}, h.libelle), h.impact && el("div", { style: "color:var(--doux);font-size:13px" }, "Si invalidée : " + h.impact)], "long"],
  ["Catégorie", h => h.categorie || "—"], ["Statut", h => [pastilleHypothese(h.statut), h.risque_id ? el("div", { style: "font-size:12.5px;color:var(--doux)" }, "→ risque créé") : null]],
  ["Qui confirme", h => h.porteur || (h.statut === "à vérifier" ? pastille("orange", "À désigner") : "—")],
  ["Échéance", h => [dateFr(h.echeance), h.statut === "à vérifier" && h.echeance && h.echeance < new Date().toISOString().slice(0, 10) ? [" ", pastille("rouge", "Dépassée")] : null]],
  ["Lot", h => (h.lot ? pastilleLot(h.lot) : "—")],
  ["", h => (h.statut === "invalidée" ? el("button", { title: "Instruire les conséquences comme une demande de changement",
    onclick: e => { e.stopPropagation(); nouvelleDemande("hypothese", h.id); } }, "Demande de changement") : "")]];
const puce = (type, objet, texte, detail, classe = "") => el("button", {
  class: "puce " + classe, title: "Modifier", onclick: () => formulaire(type, objet, recharger) },
  texte, detail && el("small", {}, detail));
const boutonAjout = (type, texte, defauts) =>
  el("button", { onclick: () => formulaire(type, null, recharger, defauts) }, texte);

// ---------- 1. Feuille de route : lots, grande temporalité, prérequis ----------
async function routeEnsemble(v) {
  const [lots, elements] = await Promise.all([api("GET", "lot"), api("GET", "lot_element")]);
  v.append(titreVue("Feuille de route",
    "Ce que chaque lot livre, quand, et ce dont il dépend. Les prérequis sont les adhérences à piloter.",
    boutonAjout("lot", "Ajouter un lot"), boutonAjout("lot_element", "Ajouter un élément", { axe: "contenu" })));
  if (!lots.length) { v.append(el("div", { class: "vide" }, "Aucun lot. Ajoutez un lot ou chargez la démo.")); return; }
  const bloc = (lot, axe, titre, classe) => {
    const liste = elements.filter(e => e.lot === lot.nom && e.axe === axe);
    return el("div", { class: "bloc " + classe }, el("h4", {}, titre),
      liste.length ? liste.map(e => puce("lot_element", e, axe === "prerequis" ? [e.libelle, " ", statutPrerequis(e.statut)] : e.libelle, e.detail))
        : el("div", { style: "color:var(--doux);font-size:14px;margin-top:6px" }, "Aucun"),
      el("button", { class: "lien", style: "margin-top:8px;font-size:13px",
        onclick: () => formulaire("lot_element", null, recharger, { lot: lot.nom, axe }) }, "Ajouter"));
  };
  v.append(el("div", { class: "defile" }, el("div", { class: "route" }, lots.map(lot =>
    el("div", { class: "lot" + (lot.date ? "" : " sans-date") },
      el("div", { class: "periode" }, lot.periode || "—"),
      el("div", { class: "axe" }),
      el("div", { class: "nom" }, pastilleLot(lot.nom),
        el("button", { class: "lien", style: "font-weight:600;color:var(--texte);text-decoration:none;font-size:16px",
          title: "Modifier le lot", onclick: () => formulaire("lot", lot, recharger) }, lot.titre || "Sans titre")),
      el("div", { style: "color:var(--doux);font-size:13px" },
        [lot.statut, lot.date && "livraison le " + dateFr(lot.date)].filter(Boolean).join(" · ")),
      bloc(lot, "contenu", "Livré dans ce lot", ""),
      bloc(lot, "prerequis", "Prérequis", "prerequis"))))));
}

// ---------- 2. Lotissement détaillé : pour qui, comment, quoi, grâce à quoi ----------
async function routeDetail(v) {
  const [lots, elements] = await Promise.all([api("GET", "lot"), api("GET", "lot_element")]);
  v.append(titreVue("Lotissement détaillé",
    "La même feuille de route, lue en phrase : pour qui, par quel canal, pour quels produits, grâce à quelles fonctionnalités — et sous quels prérequis.",
    boutonAjout("lot_element", "Ajouter un élément", { axe: "pour_qui" })));
  if (!lots.length) { v.append(el("div", { class: "vide" }, "Aucun lot.")); return; }
  const lignes = [["pour_qui", "Pour qui ?", "Clients et utilisateurs"], ["comment", "Comment ?", "Canaux"],
    ["quoi", "Quoi ?", "Produits et services"], ["fonctionnalite", "Grâce à quoi ?", "Fonctionnalités"],
    ["prerequis", "Sous quels prérequis ?", "Dépendances"]];
  v.append(el("div", { class: "cadre-table" }, el("table", {},
    el("thead", {}, el("tr", {}, el("th", {}, ""), lots.map(l => el("th", { style: "text-transform:none;font-size:14px;letter-spacing:0" },
      pastilleLot(l.nom), " ", l.titre, el("div", { style: "font-weight:400" }, l.periode || ""))))),
    el("tbody", {}, lignes.map(([axe, question, sous]) => el("tr", {},
      el("td", { style: "min-width:150px" }, el("b", {}, question), el("div", { style: "color:var(--doux);font-size:13px" }, sous)),
      lots.map(l => el("td", { style: "min-width:180px" },
        elements.filter(e => e.lot === l.nom && e.axe === axe).map(e => puce("lot_element", e, axe === "prerequis" ? [e.libelle, " ", statutPrerequis(e.statut)] : e.libelle, e.detail)),
        el("button", { class: "lien", style: "font-size:13px;margin-top:6px",
          onclick: () => formulaire("lot_element", null, recharger, { lot: l.nom, axe }) }, "Ajouter")))))))));
}

// Feuille de route : une page, deux lectures (vue d'ensemble, détail pour qui / comment / quoi).
VUES.route = ["Feuille de route", CADRE, async v => {
  const detail = etat.modeRoute === "detail";
  etat.exportVue = detail ? "lotissement" : "route";
  await (detail ? routeDetail : routeEnsemble)(v);
  const bascule = el("div", { class: "barre", role: "tablist", style: "margin-top:0" },
    [["ensemble", "Vue d'ensemble : livré et prérequis"], ["detail", "Détail : pour qui, comment, quoi"]].map(([cle, lib]) =>
      el("button", { role: "tab", "aria-selected": String((cle === "detail") === detail), class: (cle === "detail") === detail ? "principal" : "",
        onclick: () => { etat.modeRoute = cle; recharger(); } }, lib)));
  v.insertBefore(bascule, v.children[2] || null);
}];
VUES.lotissement = ["Lotissement détaillé", CADRE, v => { etat.modeRoute = "detail"; return VUES.route[2](v); }];
const STATUTS_PREREQUIS = { obtenu: "vert", "en attente": "orange", bloquant: "rouge" };
const statutPrerequis = st => (st ? pastille(STATUTS_PREREQUIS[st] || "neutre", st) : pastille("neutre", "état à préciser"));

// ---------- 3. Story map complète ----------
VUES.storymap = ["Story map", CADRE, async v => {
  const [lots, stories] = await Promise.all([api("GET", "lot"), api("GET", "story")]);
  v.append(titreVue("Story map",
    "Les étapes du parcours en colonnes, les lots en lignes. Chaque story indique si elle répond à un irritant ou porte une innovation.",
    boutonAjout("story", "Ajouter une story")));
  if (!stories.length) { v.append(el("div", { class: "vide" }, "Aucune story.")); return; }
  const etapes = [...new Set(stories.map(s => s.etape))];
  const lignes = [...lots.map(l => l.nom), ...new Set(stories.map(s => s.lot).filter(n => !lots.some(l => l.nom === n)))];
  const compte = n => stories.filter(s => s.lot === n).length;
  v.append(el("div", { class: "barre" },
    pastille("neutre", stories.length + " stories"),
    pastille("neutre", stories.filter(s => s.irritant).length + " répondent à un irritant"),
    pastille("neutre", stories.filter(s => s.innovation).length + " innovations")),
    el("div", { class: "cadre-table storymap" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, ""), etapes.map(e => el("th", { class: "etape" }, e)))),
      el("tbody", {}, lignes.map(nom => el("tr", {},
        el("th", { class: "ligne" }, pastilleLot(nom), el("div", { style: "font-weight:400;font-size:12.5px;margin-top:4px" },
          (lots.find(l => l.nom === nom)?.periode || "") + " · " + compte(nom) + " stories")),
        etapes.map(e => el("td", {}, stories.filter(s => s.etape === e && s.lot === nom).map(s =>
          el("button", { class: "story " + classeLot(nom), title: "Modifier", onclick: () => formulaire("story", s, recharger) },
            s.libelle,
            s.irritant || s.innovation ? el("span", { class: "marques" },
              [s.irritant ? "● Irritant" : "", s.innovation ? "★ Innovation" : ""].filter(Boolean).join("  ")) : null)),
          el("button", { class: "lien", style: "font-size:12.5px", onclick: () => formulaire("story", null, recharger,
            { etape: e, lot: nom, rang_etape: stories.find(s => s.etape === e)?.rang_etape }) }, "Ajouter")))))))));
}];

// ---------- 4. Macro-planning à la maille du mois ----------
const glissementJours = j => { const a = jour(j.date), b = jour(j.date_initiale); return a && b ? Math.round((a - b) / 864e5) : 0; };
const dureeLisible = n => (Math.abs(n) < 14 ? `${n} j` : `${Math.round(n / 7)} semaines`);
VUES.planning = ["Macro-planning", CADRE, async v => {
  const [activites, jalons, hyps] = await Promise.all([api("GET", "activite"), api("GET", "jalon"), api("GET", "hypothese")]);
  const hypPlanning = hyps.filter(h => h.categorie === "planning" || h.categorie === "organisation");
  v.append(titreVue("Macro-planning",
    "Les phases et les jalons à la maille du mois, avec les reports par rapport à l'engagement initial. Le planning repose sur les hypothèses ci-dessous.",
    boutonAjout("activite", "Ajouter une activité"), boutonAjout("jalon", "Ajouter un jalon")));
  const dates = [...activites.flatMap(a => [jour(a.debut), jour(a.fin)]), ...jalons.map(j => jour(j.date))].filter(Boolean);
  if (!dates.length) { v.append(el("div", { class: "vide" }, "Aucune activité ni jalon daté.")); return; }
  const min = new Date(Math.min(...dates)), max = new Date(Math.max(...dates));
  const debut = new Date(min.getFullYear(), min.getMonth(), 1);
  const fin = new Date(max.getFullYear(), max.getMonth() + 1, 1);
  const total = fin - debut, pos = d => ((d - debut) / total) * 100;
  const mois = [];
  for (let d = new Date(debut); d < fin; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) mois.push(new Date(d));
  const auj = new Date(); auj.setHours(0, 0, 0, 0);
  const reperes = () => [mois.slice(1).map(d => el("div", { class: "grille-mois", style: `left:${pos(d)}%` })),
    auj >= debut && auj < fin && el("div", { class: "aujourdhui", style: `left:${pos(auj)}%` })];
  const rang = (libelle, contenu) => el("div", { class: "rang" }, el("div", { class: "libelle" }, libelle),
    el("div", { class: "piste" }, reperes(), contenu));
  const pistes = [...new Set(activites.map(a => a.piste || "Autres"))];
  v.append(el("div", { class: "defile" }, el("div", { class: "plan", style: `min-width:${Math.max(760, 170 + mois.length * 78)}px` },
    el("div", { class: "rang" }, el("div", { class: "libelle" }, ""),
      el("div", { class: "piste" },
        el("div", { class: "mois", style: `grid-template-columns:repeat(${mois.length},1fr)` },
          mois.map(d => el("span", {}, MOIS[d.getMonth()] + " " + String(d.getFullYear()).slice(2)))),
        auj >= debut && auj < fin && el("div", { class: "aujourdhui", style: `left:${pos(auj)}%`, title: "Aujourd'hui" }))),
    rang("Jalons", jalons.filter(j => jour(j.date)).map((j, i) => {
      const g = glissementJours(j), ref = jour(j.date_initiale);
      return el("div", { class: "ligne", style: i ? "margin-top:-8px" : "" },
        g && ref && ref >= debut && ref < fin ? el("span", { class: "reference", style: `left:${pos(ref)}%`, title: `Engagement initial : ${dateFr(j.date_initiale)}` }) : null,
        el("button", { class: "jalon " + (j.statut === "atteint" ? "atteint" : "") + (pos(jour(j.date)) > 62 ? " gauche" : ""), style: `left:${pos(jour(j.date))}%`,
          title: `${j.libelle} — ${dateFr(j.date)} (${j.statut || "à venir"})` + (g ? ` · engagement initial ${dateFr(j.date_initiale)}` : ""),
          onclick: () => formulaire("jalon", j, recharger) },
          el("i", {}), `${j.libelle} · ${dateFr(j.date)}`, g > 0 ? el("span", { class: "report" }, ` · reporté de ${dureeLisible(g)}`) : null));
    })),
    pistes.map(p => rang(p, activites.filter(a => (a.piste || "Autres") === p && jour(a.debut) && jour(a.fin)).map(a => {
      const d = jour(a.debut), f = new Date(jour(a.fin).getTime() + 864e5);
      const largeur = Math.max(pos(f) - pos(d), 1.5), courte = largeur < 16, aGauche = pos(f) > 72;
      return el("div", { class: "ligne" }, el("button", { class: "tache" + (f <= auj ? " passee" : ""),
        style: `left:${pos(d)}%;width:${largeur}%`, "aria-label": a.libelle,
        title: `${a.libelle} — du ${dateFr(a.debut)} au ${dateFr(a.fin)}`, onclick: () => formulaire("activite", a, recharger) }, courte ? "" : a.libelle),
        courte && el("span", { class: "hors", style: aGauche ? `right:${100 - pos(d)}%;padding-right:6px` : `left:${pos(f)}%;padding-left:6px` }, a.libelle));
    }))))),
    hypPlanning.length ? el("div", { class: "carte", style: "margin-top:12px" }, el("b", {}, "Hypothèses du planning"),
      el("ul", { style: "margin:6px 0 0;padding-left:18px" }, hypPlanning.map(h => el("li", {}, h.libelle, " ", pastilleHypothese(h.statut))))) : null,
    el("div", { class: "barre", style: "color:var(--doux);font-size:13px" },
      el("span", {}, "◆ jalon (vert : atteint)"), el("span", {}, "· ◇ date d'engagement initiale d'un jalon reporté"),
      el("span", {}, "· barre grise : activité terminée"), el("span", {}, "· trait rouge : aujourd'hui")));
}];

// ---------- 5. Organisation : l'entreprise en adhérence avec l'équipe projet ----------
VUES.organisation = ["Organisation", CADRE, async v => {
  const acteurs = ref.acteurs;
  v.append(titreVue("Organisation",
    "L'équipe projet au centre, entourée des entités du client et des externes. Les acteurs encadrés en orange sont en adhérence avec l'équipe : ils conditionnent un livrable ou une validation. Chaque personne est ensuite utilisable dans le RACI et dans les réunions.",
    boutonAjout("acteur", "Ajouter un acteur")));
  const utilisations = nom => acteurs.filter(a => a.metier === nom).length;
  v.append(el("div", { class: "carte", style: "margin-bottom:14px" },
    el("div", { class: "barre", style: "margin:0 0 8px" }, el("b", {}, "Métiers"),
      el("span", { style: "color:var(--doux);font-size:13px" }, "Catalogue commun à l'organisation et au RACI. Cliquez sur un métier pour le renommer ou le supprimer."),
      el("button", { class: "pousse", onclick: () => formulaire("metier", null, recharger, { rang: ref.metiers.length }) }, "Ajouter un métier")),
    el("div", { class: "metiers" }, ref.metiers.map(m => el("button", { class: "pastille neutre", title: "Modifier",
      onclick: () => formulaire("metier", m, recharger) }, m.nom, utilisations(m.nom) ? ` · ${utilisations(m.nom)}` : "")))));
  if (!acteurs.length) { v.append(el("div", { class: "vide" }, "Aucun acteur.")); return; }
  const zone = (cercle, titre, sous, classe) => {
    const membres = acteurs.filter(a => a.cercle === cercle);
    const entites = [...new Set(membres.map(a => a.entite || ""))];
    return el("div", { class: "zone " + classe }, el("h3", {}, titre),
      el("div", { style: "color:var(--doux);font-size:13px" }, `${sous} · ${membres.length} acteur(s), dont ${membres.filter(a => a.adherence).length} en adhérence`),
      entites.map(e => [e && el("div", { class: "entite" }, e),
        el("div", { class: "acteurs" }, membres.filter(a => (a.entite || "") === e).map(a =>
          el("button", { class: "puce" + (a.adherence ? " lie" : ""), title: "Modifier", onclick: () => formulaire("acteur", a, recharger) },
            el("b", {}, a.role || "—"), el("small", {}, a.nom, a.metier ? [" · ", el("span", { class: "chip", style: "margin:0;font-size:11.5px" }, a.metier)] : null),
            a.adherence && el("small", { class: "lien-adh" }, "Adhérence : " + a.adherence))))]),
      el("button", { class: "lien", style: "font-size:13px;margin-top:8px", onclick: () => formulaire("acteur", null, recharger, { cercle }) }, "Ajouter"));
  };
  v.append(el("div", { class: "orga" },
    zone("métier", "Métier", "Environnement client", ""),
    zone("équipe projet", "Équipe projet", "Core team", "coeur"),
    zone("IT", "IT", "Environnement client", ""),
    zone("externe", "Externes", "Partenaires, éditeurs, utilisateurs", "externe")));
}];

// ---------- 6. Gouvernance : les instances et leurs créneaux ----------
const JOURS_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];
function creneauInstance(i) {
  const d = jour(i.premiere);
  if (!d || !i.heure) return pastille("orange", "À poser");
  if (i.recurrence === "quotidienne") return `Chaque jour ouvré à ${i.heure}`;
  return [el("b", {}, `${JOURS_FR[d.getDay()]} ${i.heure}`), el("div", { style: "color:var(--doux);font-size:12.5px" },
    (ref.recurrences[i.recurrence] || "") + (i.recurrence === "ponctuelle" ? ` le ${dateFr(i.premiere)}` : `, dès le ${dateFr(i.premiere)}`))];
}
VUES.gouvernance = ["Gouvernance", CADRE, async v => {
  const [instances, ag] = await Promise.all([api("GET", "instance"), api("GET", "agenda")]);
  const sansCreneau = instances.filter(i => !(i.premiere && i.heure) && i.recurrence !== "ponctuelle");
  const proposer = tout => async e => {
    if (tout && !confirm("Reproposer un créneau pour toutes les instances ? Les créneaux actuels seront remplacés.")) return;
    await pendant(e.target, "Calcul…", async () => {
      const r = await api("POST", "instance/proposer", { tout });
      dire(r.length ? `${r.length} créneau(x) proposé(s), sans chevauchement.` : "Toutes les instances ont déjà un créneau."); await recharger();
    });
  };
  v.append(titreVue("Gouvernance",
    "Les instances du projet : à quoi elles servent, qui y participe, à quel rythme. Le co-pilote propose des créneaux à partir du rythme des sprints, sans chevauchement ni réunion sur la pause de midi ; le fichier d'invitations s'importe dans Outlook ou Google Agenda.",
    boutonAjout("instance", "Ajouter une instance")));
  if (!instances.length) { v.append(el("div", { class: "vide" }, "Aucune instance.")); return; }
  v.append(el("div", { class: "barre" },
    el("button", { class: sansCreneau.length ? "principal" : "", onclick: proposer(false) },
      sansCreneau.length ? `Proposer des créneaux (${sansCreneau.length} à poser)` : "Proposer des créneaux"),
    el("button", { onclick: proposer(true) }, "Tout reproposer"),
    el("button", { onclick: e => telechargerFichier("/api/instance/ics", e.target) }, "Télécharger les invitations (.ics)")));
  const chantiers = [...new Set(instances.map(i => i.chantier || "Autres"))];
  v.append(el("div", { class: "cadre-table" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Instance", "Objectifs", "Participants", "Créneau", "Durée", ""].map(c => el("th", {}, c)))),
    el("tbody", {}, chantiers.map(c => [
      el("tr", { class: "domaine" }, el("td", { colspan: 6, style: "background:#fafbfc;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--doux)" }, c)),
      instances.filter(i => (i.chantier || "Autres") === c).map(i => {
        const personnes = idsDe(i.participants_ids).map(acteurParId).filter(Boolean);
        const sansEmail = personnes.filter(p => !(p.email || "").trim()).length;
        return el("tr", { class: "cliquable", tabindex: 0, title: "Modifier",
          onclick: () => formulaire("instance", i, recharger), onkeydown: e => { if (e.key === "Enter") formulaire("instance", i, recharger); } },
          el("td", { style: "font-weight:600;min-width:140px" }, i.nom, el("div", { style: "font-weight:400;color:var(--doux);font-size:12.5px" }, i.frequence || "")),
          el("td", {}, el("ul", { style: "margin:0;padding-left:18px" }, (i.objectifs || "").split("\n").filter(Boolean).map(o => el("li", {}, o)))),
          el("td", { style: "min-width:200px;max-width:320px" },
            personnes.map(p => el("span", { class: "chip", title: [p.role, p.metier, p.email].filter(Boolean).join(" · ") }, p.nom)),
            i.participants && el("div", { style: "color:var(--doux);font-size:12.5px" }, i.participants),
            !personnes.length && !i.participants ? "—" : null,
            sansEmail ? el("div", { style: "color:var(--orange);font-size:12px" }, `${sansEmail} sans e-mail : absent(s) de l'invitation`) : null),
          el("td", { style: "min-width:150px" }, creneauInstance(i)),
          el("td", { style: "white-space:nowrap" }, i.duree_min ? `${i.duree_min} min` : i.duree || "—"),
          el("td", { style: "white-space:nowrap" },
            i.recurrence !== "quotidienne" && el("button", { class: "principal", title: "Ordre du jour minuté à partir des décisions, actions, risques, jalons et attentes",
              onclick: e => { e.stopPropagation(); dialogueSeance(i.id); } }, "Préparer"), " ",
            i.premiere && i.heure ? el("button", { title: "Invitation de cette instance (.ics)",
              onclick: e => { e.stopPropagation(); telechargerFichier(`/api/instance/${i.id}/ics`, e.target); } }, ".ics") : null));
      })])))));

  const auj = new Date(); auj.setHours(0, 0, 0, 0);
  v.append(el("h3", {}, `Calendrier type du sprint — du ${dateFr(ag.debut)} au ${dateFr(ag.fin)}`),
    el("div", { class: "defile" }, el("div", { class: "agenda" }, ag.jours.map(j => el("div", { class: "jour" + (jour(j.date) < auj ? " passe" : "") },
      el("h4", {}, `${j.jour} ${dateFr(j.date).replace(/ \d{4}$/, "")}`),
      j.seances.map(s => el("button", { class: "seance", title: "Modifier l'instance",
        onclick: () => { const i = instances.find(x => x.id === s.id); if (i) formulaire("instance", i, recharger); } },
        el("b", {}, `${s.debut} – ${s.fin}`), s.nom)))))),
    (ag.hors_sprint.length || ag.non_planifiees.length) ? el("p", { class: "aide", style: "margin-top:8px" },
      ag.hors_sprint.length ? "Hors de ce sprint : " + ag.hors_sprint.map(h => `${h.nom} le ${dateFr(h.date)} à ${h.heure}`).join(" ; ") + ". " : "",
      ag.non_planifiees.length ? "Sans créneau : " + ag.non_planifiees.map(n => n.nom).join(", ") + "." : "") : null);
}];

// ---------- 7. Rappel : déroulé d'un sprint et KPI à collecter ----------
const KPI_A_COLLECTER = [
  ["Backlog projet", "Stock de user stories dans leurs différents états.", "Outil de tickets"],
  ["Backlog du lot", "Stock de stories restant à réaliser pour le lot en cours, en story points.", "Reste à faire du sprint"],
  ["Vélocité", "Story points réalisés pendant le sprint, comparés au prévu.", "Points prévus et réalisés"],
  ["Capacité", "Jours-homme réalisables sur le sprint, selon les jours ouvrés et les absences.", "Capacité du sprint"],
  ["Qualité", "Anomalies créées et corrigées ; temps de correction rapporté au temps de développement.", "Anomalies créées et corrigées"],
  ["Prédictibilité", "Capacité à planifier les livraisons : taux de réalisation moyen sur les derniers sprints.", "Calculé"],
  ["Moral", "État d'esprit de l'équipe, de 1 à 5, et demandes éventuelles.", "Moral du sprint"],
  ["Périmètre", "Points ajoutés au backlog pendant le sprint, comparés à la marge prévue.", "Points ajoutés"],
];
VUES.sprintkpi = ["Sprint et KPI", CADRE, async v => {
  const [instances, m, s] = await Promise.all([api("GET", "instance"), api("GET", "mission"), api("GET", "synthese")]);
  const duree = (motif, defaut) => instances.find(i => new RegExp(motif, "i").test(i.nom))?.duree || defaut;
  const rite = (nom, texte, d) => el("div", { class: "rite" }, el("b", {}, nom, d && [" ", pastille("neutre", d)]), el("span", {}, texte));
  v.append(titreVue("Sprint et KPI",
    `Rappel du fonctionnement : un sprint dure ${Math.round((m.duree_sprint_jours || 14) / 7)} semaines. Les KPI se collectent en fin de sprint et se présentent à la démonstration.`),
    el("div", { class: "sprint" },
      el("div", { class: "phase" }, el("h4", {}, "Début de sprint"),
        rite("Planification de sprint", "Définir avec l'équipe le travail du sprint et estimer l'effort.", duree("planif", "1 h 30"))),
      el("div", { class: "phase" }, el("h4", {}, "Pendant le sprint"),
        rite("Mêlée quotidienne", "Travail de la veille, travail du jour, points bloquants.", duree("mêlée|daily", "15 min")),
        rite("Affinage du backlog", "Affiner les stories à venir et vérifier qu'elles sont prêtes (DoR).", duree("affinage|refinement", "2 × 1 h")),
        rite("Synchro hebdo", "Alignement avec les équipes en adhérence ; ce qui doit remonter au comité sponsor.", duree("synchro|weekly", "30 min à 1 h"))),
      el("div", { class: "phase" }, el("h4", {}, "Fin de sprint"),
        rite("Collecte des KPI", "Relever les chiffres du sprint avant la démonstration.", null),
        rite("Démonstration", "Présenter les travaux, les indicateurs et le planning ; recueillir le feedback.", duree("démo", "1 h")),
        rite("Rétrospective", "Bilan du fonctionnement de l'équipe et plans d'action.", duree("rétro", "1 h 30")))),
    el("div", { class: "carte", style: "margin-top:10px" }, el("b", {}, "Hors sprint — Comité sponsor "), pastille("neutre", duree("comité|sponsor", "1 h")),
      el("div", { style: "color:var(--doux)" }, "Valider les orientations métier et techniques, arbitrer les décisions structurantes.")),
    el("h3", {}, "KPI à collecter à chaque sprint"),
    el("div", { class: "cadre-table" }, el("table", {},
      el("thead", {}, el("tr", {}, ["KPI", "Définition", "Où il est saisi"].map(c => el("th", {}, c)))),
      el("tbody", {}, KPI_A_COLLECTER.map(([nom, def, ou]) => el("tr", {},
        el("td", { style: "font-weight:600;white-space:nowrap" }, nom), el("td", {}, def), el("td", { style: "color:var(--doux)" }, ou)))))),
    el("div", { class: "barre" },
      el("button", { class: "principal", onclick: () => afficher("sprints") }, s.kpi ? `Saisir le sprint ${s.kpi.sprint + 1}` : "Saisir le premier sprint"),
      el("button", { onclick: () => afficher("kpi") }, "Voir les indicateurs")));
}];

// ---------- 8. RACI ----------
// Colonnes : des métiers du catalogue ("metier:<nom>") et/ou des personnes de l'organisation ("acteur:<id>").
const cleRaci = k => (String(k).includes(":") ? String(k) : "metier:" + k);
function colonneRaci(cle) {
  const [genre, val] = cle.split(/:(.*)/s);
  if (genre === "acteur") {
    const a = acteurParId(val);
    return { titre: a ? a.nom : "Personne supprimée", precision: a ? (a.metier || a.role || "") : "", personne: true };
  }
  const noms = ref.acteurs.filter(a => a.metier === val).map(a => a.nom);
  return { titre: val, precision: noms.slice(0, 2).join(", ") + (noms.length > 2 ? ` +${noms.length - 2}` : ""), personne: false };
}
function choisirColonnesRaci(actuelles) {
  const d = $("#dialogue");
  const cases = cle => el("input", { type: "checkbox", value: cle, checked: actuelles.includes(cle) });
  const groupe = (titre, items) => el("div", {}, el("div", { style: "font-weight:600;margin-bottom:4px" }, titre),
    el("div", { class: "personnes", style: "max-height:220px" }, items));
  d.replaceChildren(el("form", { method: "dialog", onsubmit: async e => {
    e.preventDefault();
    const cochees = [...d.querySelectorAll("input:checked")].map(c => c.value);
    const ordre = [...actuelles.filter(c => cochees.includes(c)), ...cochees.filter(c => !actuelles.includes(c))];
    try { await api("PUT", "mission", { raci_roles: ordre }); d.close(); await recharger(); }
    catch (err) { dire(err.message, true); }
  } },
    el("h3", {}, "Colonnes du RACI"),
    el("p", { class: "aide", style: "margin:0" }, "Choisissez des métiers, des personnes, ou les deux. Une colonne métier regroupe toutes les personnes qui l'exercent ; une colonne personne désigne quelqu'un nommément."),
    groupe("Métiers", ref.metiers.map(m => el("label", { class: "case", style: "font-size:14px" }, cases("metier:" + m.nom), m.nom,
      el("span", { style: "color:var(--doux)" }, ` · ${ref.acteurs.filter(a => a.metier === m.nom).length}`)))),
    groupe("Personnes de l'organisation", ref.acteurs.map(a => el("label", { class: "case", style: "font-size:14px" }, cases("acteur:" + a.id), a.nom,
      el("span", { style: "color:var(--doux)" }, " · " + (a.metier || a.role || ""))))),
    el("div", { class: "barre" }, el("span", { class: "pousse" }),
      el("button", { type: "button", onclick: () => d.close() }, "Annuler"), el("button", { class: "principal" }, "Enregistrer"))));
  d.showModal();
}
VUES.raci = ["RACI", CADRE, async v => {
  const [lignes, m] = await Promise.all([api("GET", "raci"), api("GET", "mission")]);
  const colonnes_ = (m.raci_roles || []).map(cleRaci);
  v.append(titreVue("RACI",
    "Qui réalise, qui approuve, qui est consulté, qui est informé. Les colonnes viennent du catalogue de métiers et des personnes de l'organisation. Cliquez sur une case pour changer sa valeur. Règle : un seul A par activité, et au moins un R.",
    el("button", { onclick: () => choisirColonnesRaci(colonnes_) }, "Choisir les colonnes"), boutonAjout("raci", "Ajouter une activité")));
  if (!colonnes_.length || !lignes.length) { v.append(el("div", { class: "vide" }, "Choisissez les colonnes puis ajoutez des activités, ou chargez la démo.")); return; }
  const CYCLE = ["", "R", "A", "C", "I"];
  const domaines = [...new Set(lignes.map(l => l.domaine || "Autres"))];
  const valeurs = l => {
    let brut = {};
    try { brut = JSON.parse(l.valeurs || "{}") || {}; } catch (e) { /* valeur illisible : ligne vide */ }
    return Object.fromEntries(Object.entries(brut).map(([k, x]) => [cleRaci(k), x]));
  };
  v.append(el("div", { class: "barre raci", style: "font-size:13.5px" },
    [["R", "Réalise"], ["A", "Approuve"], ["C", "Est consulté"], ["I", "Est informé"]].map(([k, t]) =>
      el("span", {}, el("span", { class: "pastille " + k, style: "border-radius:6px" }, k), " " + t)),
    el("span", { style: "color:var(--doux)" }, "· en-tête souligné : personne nommée")),
    el("div", { class: "cadre-table raci" }, el("table", {},
      el("thead", {}, el("tr", {}, el("th", {}, "Activité"), colonnes_.map(cle => {
        const c = colonneRaci(cle);
        return el("th", { class: "c", title: c.precision }, el("span", { style: c.personne ? "text-decoration:underline" : "" }, c.titre),
          c.precision && el("div", { style: "text-transform:none;letter-spacing:0;font-weight:400;font-size:11px" }, c.precision));
      }), el("th", {}, "Contrôle"))),
      el("tbody", {}, domaines.map(d => [
        el("tr", { class: "domaine" }, el("td", { colspan: colonnes_.length + 2 }, d)),
        lignes.filter(l => (l.domaine || "Autres") === d).map(l => {
          const val = valeurs(l), liste = colonnes_.map(c => val[c]).filter(Boolean);
          const nbA = liste.filter(x => x === "A").length, nbR = liste.filter(x => x === "R").length;
          const souci = nbA !== 1 ? (nbA ? nbA + " approbateurs" : "Aucun approbateur") : !nbR ? "Aucun réalisateur" : null;
          return el("tr", {},
            el("td", { style: "min-width:200px" }, el("button", { class: "lien", style: "color:var(--texte);text-decoration:none;text-align:left",
              title: "Modifier l'activité", onclick: () => formulaire("raci", l, recharger) }, l.activite)),
            colonnes_.map(cle => el("td", { class: "c" }, el("button", { class: val[cle] || "",
              "aria-label": `${l.activite}, ${colonneRaci(cle).titre} : ${val[cle] || "aucun"}`,
              onclick: async () => {
                const suivant = CYCLE[(CYCLE.indexOf(val[cle] || "") + 1) % CYCLE.length];
                const nv = { ...val }; if (suivant) nv[cle] = suivant; else delete nv[cle];
                try { await api("PUT", `raci/${l.id}`, { valeurs: JSON.stringify(nv) }); await recharger(); }
                catch (e) { dire(e.message, true); }
              } }, val[cle] || "·"))),
            el("td", {}, souci ? pastille("orange", souci) : pastille("vert", "OK")));
        })])))));
}];

// ---------- Fiche mission ----------
VUES.mission = ["Fiche mission", CADRE, async v => {
  const [m, livrables, hyps] = await Promise.all([api("GET", "mission"), api("GET", "livrable"), api("GET", "hypothese")]);
  const champ = (cle, lib, genre = "text", large = false) => {
    const s = genre === "long" ? el("textarea", { name: cle }) : el("input", { name: cle, type: genre });
    s.value = m[cle] ?? "";
    return el("label", { class: large ? "large" : "" }, lib, s);
  };
  v.append(titreVue("Fiche mission", "Sur quoi la mission s'est engagée : objectifs et porteurs des trois dimensions du pilotage, date cible, et les hypothèses sur lesquelles reposent le planning et le chiffrage."),
    el("form", { class: "carte", onsubmit: async e => {
      e.preventDefault();
      const corps = Object.fromEntries(new FormData(e.target));
      corps.duree_sprint_jours = Number(corps.duree_sprint_jours) || 14;
      try { await api("PUT", "mission", corps); dire("Fiche mission enregistrée."); await entete(); }
      catch (err) { dire(err.message, true); }
    } }, el("div", { class: "champs" },
      champ("nom", "Nom de la mission"), champ("client", "Client"),
      champ("objectif_business", "Objectif business", "long"), champ("porteur_business", "Porteur business"),
      champ("objectif_solution", "Objectif solution", "long"), champ("porteur_solution", "Porteur solution"),
      champ("objectif_projet", "Objectif projet", "long"), champ("porteur_projet", "Porteur projet"),
      champ("date_cible", "Date cible", "date"), champ("duree_sprint_jours", "Durée d'un sprint (jours)", "number")),
      el("div", { class: "barre" }, el("button", { class: "principal pousse" }, "Enregistrer"))),
    section("Hypothèses", "hypothese", hyps, colonnesHypotheses, recharger),
    el("p", { class: "aide", style: "margin-top:6px" }, "Une hypothèse invalidée crée le risque correspondant dans le suivi des risques."),
    section("Livrables de pilotage", "livrable", livrables, [
      ["Chantier", l => l.chantier || "—"], ["Livrable", l => l.libelle],
      ["Avancement", l => (l.avancement == null ? "—" : l.avancement + " %"), "num"],
      ["Statut", l => l.statut || "—", "long"], ["Tendance", l => tendance(l.tendance)]], recharger));
}];
