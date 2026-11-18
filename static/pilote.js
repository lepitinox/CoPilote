"use strict";
// Pages du quotidien du pilote : ce qu'il y a à traiter, et la préparation d'une séance.
const AUJOURDHUI = "Aujourd'hui";
const GROUPES_A_TRAITER = {
  maintenant: ["Maintenant", "Retards et points critiques : à traiter avant tout le reste."],
  semaine: ["Cette semaine", "Échéances des sept prochains jours, réunions à préparer, saisies attendues."],
  surveiller: ["À surveiller", "Rien d'urgent, mais à ne pas laisser dériver."],
};
const GENRES = { action: "Action", decision: "Décision", risque: "Risque", jalon: "Jalon", facture: "Facturation",
  attente: "Client", compte_rendu: "Compte rendu", sprint: "Sprint", meteo: "Météo", reunion: "Réunion",
  hypothese: "Hypothèse", prerequis: "Prérequis", changement: "Changement" };

VUES.aujourdhui = ["À traiter", AUJOURDHUI, async v => {
  const t = await api("GET", "a_traiter"), dem = t.demarrage;
  v.append(titreVue("À traiter",
    "Ce que la mission attend de vous, du plus urgent au moins urgent. Chaque ligne s'ouvre d'un clic ; les boutons agissent directement et chaque action est inscrite à l'historique."));
  if (dem.faites < dem.total) {
    v.append(el("details", { class: "carte", open: dem.faites < dem.total - 2, style: "margin-bottom:16px" },
      el("summary", { style: "cursor:pointer;font-weight:600" }, `Démarrage de la mission : ${dem.faites} / ${dem.total} étapes posées`),
      el("p", { class: "aide", style: "margin:8px 0" }, "Ce qu'il faut poser pour que le co-pilote puisse calculer le délai, le budget et la satisfaction du client, et vous alerter."),
      el("div", { class: "liste" }, dem.etapes.filter(e => !e.fait).map(e => el("div", { class: "item" },
        el("div", { class: "tete" }, pastille("neutre", "à faire"), el("span", { class: "titre" }, e.titre),
          el("button", { style: "margin-left:auto", onclick: () => afficher(e.vue) }, "Y aller")),
        el("div", { class: "detail" }, e.aide)))),
      el("p", { class: "aide", style: "margin:8px 0 0" }, "Déjà posé : " + dem.etapes.filter(e => e.fait).map(e => e.titre.split(" :")[0].toLowerCase()).join(", ") + ".")));
  }
  v.append(el("div", { class: "grille" }, Object.entries(GROUPES_A_TRAITER).map(([g, [lib]]) =>
    tuile(lib, nb(t.compte[g]), g === "maintenant" && t.compte[g] ? pastille("rouge", "à traiter en priorité") : ""))));
  if (!t.items.length) { v.append(el("div", { class: "vide", style: "margin-top:16px" }, "Rien à traiter : la mission est à jour.")); return; }
  const agir = async (a, bouton) => {
    if (a.seance) return dialogueSeance(a.seance);
    await pendant(bouton, "…", async () => { await api("PUT", `${a.table}/${a.id}`, a.champs); dire(`${a.libelle} : fait.`); await recharger(); });
  };
  const ouvrir = async it => {
    if (it.vue) return afficher(it.vue);
    if (it.table === "instance") return dialogueSeance(it.id);
    const objet = await api("GET", it.table).then(l => l.find(x => x.id === it.id));
    if (objet) formulaire(it.table, objet, recharger);
  };
  for (const [g, [lib, aide]] of Object.entries(GROUPES_A_TRAITER)) {
    const liste = t.items.filter(i => i.groupe === g);
    if (!liste.length) continue;
    v.append(el("h3", {}, `${lib} (${liste.length})`), el("p", { class: "aide", style: "margin:-4px 0 8px" }, aide), el("div", { class: "liste" }, liste.map(it =>
      el("div", { class: "item cliquable", tabindex: 0, onclick: () => ouvrir(it), onkeydown: e => { if (e.key === "Enter") ouvrir(it); } },
        el("div", { class: "tete" }, pastille(g === "maintenant" ? "rouge" : g === "semaine" ? "orange" : "neutre", GENRES[it.genre] || it.genre),
          el("span", { class: "titre" }, it.titre),
          el("span", { class: "pousse", style: "margin-left:auto;display:flex;gap:6px" }, it.actions.map(a =>
            el("button", { onclick: e => { e.stopPropagation(); agir(a, e.currentTarget); } }, a.libelle)))),
        it.detail && el("div", { class: "detail" }, it.detail)))));
  }
}];

// ---------- Préparer une séance ----------
function texteSeance(s) {
  const lignes = [`# ${s.instance.nom}${s.date ? " — " + dateFr(s.date) + (s.instance.heure ? " à " + s.instance.heure : "") : ""}`, "",
    `Durée : ${s.duree} min · Participants : ${[...s.participants, s.autres_participants].filter(Boolean).join(", ") || "—"}`, ""];
  if (s.messages_cles.length) lignes.push("## Messages clés", ...s.messages_cles.map(m => "- " + m), "");
  lignes.push("## Ordre du jour");
  for (const p of s.ordre_du_jour) {
    lignes.push(`${p.minutes ? p.minutes + " min — " : ""}**${p.titre}**`, ...p.contenu.map(c => "  - " + c));
  }
  return lignes.join("\n");
}

async function dialogueSeance(ident) {
  const d = $("#dialogue");
  let s;
  try { s = await api("GET", `instance/${ident}/seance`); } catch (e) { dire(e.message, true); return; }
  d.classList.add("large");
  if (!d.dataset.nettoyageSeance) {
    d.dataset.nettoyageSeance = "1";
    d.addEventListener("close", () => d.classList.remove("large"));
  }
  let debut = s.instance.heure ? agendaMinutes(s.instance.heure) : null;
  const horaire = p => { if (debut == null || !p.minutes) return ""; const h = enHeure(debut); debut += p.minutes; return h; };
  d.replaceChildren(el("form", { method: "dialog" },
    el("div", { class: "barre", style: "margin:0" }, el("h3", {}, `Préparer : ${s.instance.nom}`), pastille("neutre", s.type_libelle)),
    el("p", { class: "aide", style: "margin:0" },
      (s.date ? `Prochaine séance le ${dateFr(s.date)}${s.instance.heure ? " à " + s.instance.heure : ""}` : "Pas de créneau posé")
      + ` · ${s.duree} min · ${[...s.participants, s.autres_participants].filter(Boolean).join(", ") || "participants non renseignés"}`),
    s.messages_cles.length ? el("div", { class: "carte" }, el("b", {}, "Messages clés"),
      el("ul", { style: "margin:6px 0 0;padding-left:18px" }, s.messages_cles.map(m => el("li", {}, m)))) : null,
    s.ordre_du_jour.length ? el("div", { class: "cadre-table" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Heure", "Durée", "Point", "Contenu"].map(x => el("th", {}, x)))),
      el("tbody", {}, s.ordre_du_jour.map(p => el("tr", {},
        el("td", { style: "white-space:nowrap;color:var(--doux)" }, horaire(p)),
        el("td", { class: "num" }, p.minutes ? p.minutes + " min" : "—"),
        el("td", { style: "font-weight:600;min-width:160px" }, p.titre),
        el("td", {}, p.contenu.length ? el("ul", { style: "margin:0;padding-left:18px" }, p.contenu.map(c => el("li", {}, c))) : "—"))))))
      : el("div", { class: "vide" }, "Rien à préparer pour ce type de séance : c'est un point d'équipe court."),
    s.depassement_minutes ? el("div", { class: "bandeau" }, `L'ordre du jour dépasse la durée prévue de ${s.depassement_minutes} min.`) : null,
    el("div", { class: "barre" },
      el("button", { type: "button", onclick: e => telechargerFichier(`/api/export/seance.pptx?instance=${ident}`, e.currentTarget) }, "PowerPoint"),
      el("button", { type: "button", onclick: async () => {
        try { await navigator.clipboard.writeText(texteSeance(s)); dire("Ordre du jour copié : collez-le dans l'invitation ou un e-mail."); }
        catch (e) { dire("Copie impossible depuis ce navigateur.", true); }
      } }, "Copier le texte"),
      el("span", { class: "pousse" }), el("button", { class: "principal" }, "Fermer"))));
  if (!d.open) d.showModal();
}
const agendaMinutes = h => { const m = /^(\d{1,2}):(\d{2})/.exec(h || ""); return m ? +m[1] * 60 + +m[2] : null; };
const enHeure = m => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

// Indicateurs : le rappel du sprint et des KPI à collecter est rangé en bas de page, repliable.
{
  const indicateurs = VUES.kpi[2];
  VUES.kpi[2] = async v => {
    await indicateurs(v);
    const rappel = el("div", {});
    await VUES.sprintkpi[2](rappel);
    rappel.firstElementChild?.remove();  // barre de titre et exports de la page d'origine
    v.append(el("details", { class: "carte", style: "margin-top:16px" },
      el("summary", { style: "cursor:pointer;font-weight:600" }, "Comment fonctionne un sprint et quels KPI collecter"), rappel));
  };
}

// ---------- Tableau de bord : les trois réponses, ce qui est à traiter, la synthèse repliée ----------
VUES.tableau = ["Tableau de bord", AUJOURDHUI, async v => {
  etat.exportVue = "synthese";
  const s = await api("GET", "synthese");
  v.append(titreVue("Tableau de bord — " + s.semaine,
    "En haut, les trois réponses au sponsor ; dessous, ce que la mission attend de vous. Le détail de la synthèse (décisions à obtenir, tendance, livraison, alertes) se déplie en bas de page."));
  v.append(el("div", { class: "reponses compactes" }, [["delai", "Délai", "planning"], ["budget", "Budget", "budget"], ["client", "Client", "attentes"]].map(([c, t, vue]) => {
    const r = s.reponses[c];
    return el("div", { class: "carte reponse cliquable " + r.etat, tabindex: 0, title: "Ouvrir le détail",
      onclick: () => afficher(vue), onkeydown: e => { if (e.key === "Enter") afficher(vue); } },
      el("h3", {}, t, r.etat === "inconnu" ? pastille("neutre", "Non mesurable") : pastille(r.etat, ETATS_REPONSE[r.etat])),
      el("div", {}, r.phrase));
  })));
  const aTraiter = el("div", { style: "margin-top:12px" });
  await VUES.aujourdhui[2](aTraiter);
  [...aTraiter.children].slice(0, 2).forEach(x => x.remove());  // titre et aide de la page intégrée
  aTraiter.querySelector(":scope > .grille")?.remove();  // les comptes sont dans les titres de groupe
  aTraiter.querySelectorAll(":scope > p.aide").forEach(p => p.remove());
  const surveiller = [...aTraiter.querySelectorAll(":scope > h3")].find(h => h.textContent.startsWith("À surveiller"));
  if (surveiller) {
    const liste = surveiller.nextElementSibling;
    const repli = el("details", { class: "section" }, el("summary", {}, surveiller.textContent), liste);
    surveiller.replaceWith(repli);
  }
  v.append(aTraiter);
  const detail = el("div", {});
  await VUES.synthese[2](detail);
  detail.querySelector(".reponses")?.remove();
  [...detail.children].slice(0, 2).forEach(x => x.remove());
  v.append(el("details", { class: "section" },
    el("summary", {}, `Synthèse détaillée : décisions à obtenir, tendance, livraison, ${s.alertes.length} alerte(s)`), detail));
}];

// ---------- Saisir : sprints, temps et dépenses, comptes rendus, historique, en onglets ----------
VUES.saisie = ["Saisir", SAISIE, async v => {
  const o = ONGLETS_SAISIE.some(([c]) => c === etat.ongletSaisie) ? etat.ongletSaisie : "sprints";
  v.append(el("div", { class: "barre", role: "tablist", style: "margin-top:0" }, ONGLETS_SAISIE.map(([c, l]) =>
    el("button", { role: "tab", "aria-selected": String(c === o), class: c === o ? "principal" : "",
      onclick: () => { etat.ongletSaisie = c; recharger(); } }, l))));
  etat.exportVue = o;
  await VUES[o][2](v);
}];
