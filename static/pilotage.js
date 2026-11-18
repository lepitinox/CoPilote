"use strict";
// Vues de pilotage : synthèse, suivi des risques, décisions, météo ; et vues de saisie.
const PILOTAGE = "Pilotage", SAISIE = "Saisie";

const ETATS_REPONSE = { vert: "Vert", orange: "Orange", rouge: "Rouge", inconnu: "Non mesurable" };
VUES.synthese = ["Synthèse", PILOTAGE, async v => {
  const s = await api("GET", "synthese"), k = s.kpi, a = s.atterrissage;
  v.append(titreVue("Synthèse — " + s.semaine,
    "Les trois questions d'un sponsor : tient-on le délai, le budget, le client est-il satisfait ? Puis les décisions à obtenir. Tous les chiffres sont calculés à partir des données saisies."));
  v.append(el("div", { class: "reponses" }, [["delai", "Délai", "planning"], ["budget", "Budget", "budget"], ["client", "Client", "attentes"]].map(([c, t, vue]) => {
    const r = s.reponses[c];
    return el("div", { class: "carte reponse cliquable " + r.etat, tabindex: 0, title: "Ouvrir le détail", onclick: () => afficher(vue),
      onkeydown: e => { if (e.key === "Enter") afficher(vue); } },
      el("h3", {}, t, r.etat === "inconnu" ? pastille("neutre", ETATS_REPONSE.inconnu) : pastille(r.etat, ETATS_REPONSE[r.etat])),
      el("div", {}, r.phrase), r.details.length ? el("ul", {}, r.details.map(x => el("li", {}, x))) : null);
  })));
  const enAttente = s.decisions_en_attente;
  v.append(el("h3", {}, "Décisions à obtenir"), enAttente.length ? el("div", { class: "cadre-table" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Décision", "Décideur", "Échéance", "En attente depuis"].map(x => el("th", {}, x)))),
    el("tbody", {}, enAttente.map(d => el("tr", { class: "cliquable", tabindex: 0, onclick: () => formulaire("decision", d, recharger) },
      el("td", { class: "long" }, el("b", {}, d.titre)), el("td", {}, d.porteur || pastille("orange", "À désigner")),
      el("td", {}, dateFr(d.echeance), d.en_retard ? [" ", pastille("rouge", "En retard")] : null),
      el("td", { class: "num" }, d.age_jours == null ? "—" : d.age_jours + " j"))))))
    : el("div", { class: "vide" }, "Aucune décision en attente."));
  if (s.tendances.length) v.append(el("h3", {}, "Tendance des dernières semaines"), el("div", { class: "frise" },
    s.tendances.map(x => el("span", { title: `${x.semaine} (météo du ${dateFr(x.date)})` }, tendance(x.tendance))),
    el("span", { style: "color:var(--doux);font-size:13px;margin-left:6px" }, "→ aujourd'hui :"), tendance(s.tendance)));
  v.append(el("h3", {}, "Livraison"));
  if (!k) {
    v.append(el("p", { class: "aide" }, "Aucun sprint saisi : la livraison se lit sur les jalons (vue Macro-planning)."));
  } else {
    let fin = "Non calculable", note = "Le backlog ne se vide pas assez vite";
    if (a.atteignable) {
      fin = dateFr(a.date_fin_estimee);
      note = a.ecart_sprints == null ? "Pas de date cible" : a.ecart_sprints === 0 ? "Dans la cible du " + dateFr(a.date_cible)
        : `+${a.ecart_sprints} sprints après la cible du ${dateFr(a.date_cible)}`;
    }
    v.append(el("div", { class: "grille" },
      tuile("Fin estimée", fin, note),
      tuile(`Sprint ${k.sprint} : réalisé / prévu`, `${nb(k.realise)} / ${nb(k.prevu)}`, pct(k.taux_realisation)),
      tuile("Reste à faire", nb(k.reste) + " pts", `Consommation nette : ${nb(a.consommation_nette)} pts par sprint`),
      tuile("Points ajoutés", nb(k.ajoute), `Moyenne : ${nb(k.ajout_moyen)} · marge : ${nb(s.seuils.marge_ajout)}`),
      tuile("Moral", k.moral ? k.moral + " / 5" : "—", `Anomalies : ${k.anomalies_creees} créées, ${k.anomalies_corrigees} corrigées`)));
  }
  v.append(el("h3", {}, `Alertes (${s.alertes.length})`, " ", tendance(s.tendance)));
  v.append(s.alertes.length ? el("div", { class: "liste" }, s.alertes.map(x => el("div", { class: "item" },
    el("div", { class: "tete" }, pastille(x.niveau >= 3 ? "rouge" : "orange", x.niveau >= 3 ? "Niveau 3 — sponsor" : "Niveau 2 — projet"),
      el("span", { class: "titre" }, x.titre)),
    el("div", { class: "detail" }, x.detail))))
    : el("div", { class: "vide" }, "Aucun déclencheur atteint."));
  v.append(el("p", { class: "aide", style: "margin-top:12px" }, "Ce que vous avez à faire : ",
    el("button", { class: "lien", onclick: () => afficher("aujourdhui") }, "ouvrir la page À traiter"), "."));
}];

// ---------- Suivi des risques : risque, état, évolution depuis la dernière session ----------
const EVOLUTIONS = {
  hausse: ["↗ En hausse", "rouge"], baisse: ["↘ En baisse", "vert"], stable: ["→ Stable", "neutre"],
  nouveau: ["✚ Nouveau", "orange"], clos: ["✓ Clos", "vert"],
};
VUES.risques = ["Suivi des risques", PILOTAGE, async v => {
  const s = await api("GET", "suivi_risques");
  v.append(titreVue("Suivi des risques",
    s.reference ? `Évolution calculée par rapport à la dernière session : ${s.reference.semaine}, météo du ${dateFr(s.reference.date)}.`
      : "Aucune session précédente enregistrée : l'évolution affichée est celle saisie à la main. Elle sera calculée dès qu'une météo aura été générée.",
    boutonAjout("risque", "Ajouter un risque ou une adhérence")));
  if (!s.risques.length) { v.append(el("div", { class: "vide" }, "Registre vide.")); return; }
  const ouverts = s.risques.filter(r => r.etat !== "clos"), clos = s.risques.filter(r => r.etat === "clos");
  const lettres = new Map(ouverts.map((r, i) => [r.id, String.fromCharCode(65 + (i % 26))]));
  const compte = e => s.risques.filter(r => r.evolution_session === e).length;
  v.append(el("div", { class: "grille" },
    tuile("Ouverts", nb(ouverts.length), `dont ${ouverts.filter(r => r.criticite >= 6).length} de criticité élevée`),
    tuile("En hausse", nb(compte("hausse")), "depuis la dernière session"),
    tuile("Nouveaux", nb(compte("nouveau"))),
    tuile("En baisse ou clos", nb(compte("baisse") + compte("clos")))));

  const ETATS = { ouvert: "orange", "en traitement": "neutre", clos: "vert" };
  const ligne = r => {
    const [texte, classe] = EVOLUTIONS[r.evolution_session] || EVOLUTIONS.stable;
    const detail = r.evolution_source === "saisie" ? "saisie manuelle"
      : r.criticite_precedente != null && r.criticite_precedente !== r.criticite ? `criticité ${r.criticite_precedente} → ${r.criticite}`
      : r.etat_precedent && r.etat_precedent !== r.etat ? `était « ${r.etat_precedent} »` : null;
    return el("tr", { class: "cliquable", tabindex: 0, title: "Modifier", onclick: () => formulaire("risque", r, recharger),
      onkeydown: e => { if (e.key === "Enter") formulaire("risque", r, recharger); } },
      el("td", {}, lettres.has(r.id) ? el("span", { class: "lettre" }, lettres.get(r.id)) : "—"),
      el("td", { class: "long" }, el("b", {}, r.titre), el("div", { style: "color:var(--doux);font-size:13.5px" },
        (r.nature === "adherence" ? "Adhérence" : "Risque") + (r.description ? " — " + r.description.split("\n")[0] : ""))),
      el("td", {}, pastille(ETATS[r.etat] || "neutre", r.etat || "—")),
      el("td", {}, el("span", { class: "pastille evo " + classe }, texte), detail && el("div", { style: "color:var(--doux);font-size:12.5px;margin-top:2px" }, detail)),
      el("td", {}, r.criticite ? pastille(r.criticite >= 6 ? "rouge" : r.criticite >= 3 ? "orange" : "vert", r.criticite + " / 9") : "—"),
      el("td", {}, r.lot ? pastilleLot(r.lot.trim()) : "—"),
      el("td", {}, r.porteur || pastille("orange", "Sans porteur")),
      el("td", { style: "white-space:nowrap" }, dateFr(r.echeance)));
  };
  const table = lignes => el("div", { class: "cadre-table" }, el("table", {},
    el("thead", {}, el("tr", {}, ["ID", "Risque", "État", "Évolution depuis la dernière session", "Criticité", "Lot impacté", "Porteur", "Échéance"].map(c => el("th", {}, c)))),
    el("tbody", {}, lignes.map(ligne))));

  const fond = (p, i) => (p * i >= 6 ? "var(--rouge-fond)" : p * i >= 3 ? "var(--orange-fond)" : "var(--vert-fond)");
  const NIV = ["Faible", "Moyenne", "Forte"];
  const matrice = el("div", { class: "matrice" },
    [3, 2, 1].map(i => [el("div", { class: "axe-y" }, "Impact " + ["faible", "moyen", "fort"][i - 1]),
      [1, 2, 3].map(p => el("div", { class: "case", style: "background:" + fond(p, i) },
        ouverts.filter(r => r.probabilite === p && r.impact === i).map(r =>
          el("span", { class: "lettre", title: r.titre }, lettres.get(r.id)))))]),
    el("div", {}), NIV.map(n => el("div", { class: "axe-x" }, "Probabilité " + n.toLowerCase())));
  const horsMatrice = ouverts.filter(r => !(r.probabilite >= 1 && r.probabilite <= 3 && r.impact >= 1 && r.impact <= 3));
  v.append(el("h3", {}, "Risques et adhérences ouverts"), table(ouverts.length ? ouverts : []),
    el("h3", {}, "Matrice probabilité × impact"),
    el("div", { class: "carte", style: "display:inline-block;max-width:100%" }, matrice,
      horsMatrice.length ? el("div", { style: "color:var(--doux);font-size:13px;margin-top:8px" },
        "Non positionnés (probabilité ou impact manquant) : " + horsMatrice.map(r => lettres.get(r.id)).join(", ")) : null),
    clos.length ? [el("h3", {}, "Clos"), table(clos)] : null);
}];

VUES.decisions = ["Décisions et actions", PILOTAGE, async v => {
  const lignes = await api("GET", "decision"), auj = new Date().toISOString().slice(0, 10);
  const ouvert = l => l.statut === "à prendre" || l.statut === "à faire";
  const cols = [
    ["Titre", l => l.titre, "long"], ["Statut", l => l.statut || "—"],
    ["Décideur ou porteur", l => l.porteur || pastille("orange", "Non désigné")],
    ["Échéance", l => [dateFr(l.echeance), ouvert(l) && l.echeance && l.echeance < auj ? [" ", pastille("rouge", "En retard")] : null]],
    ["Instance", l => l.instance || "—"]];
  v.append(titreVue("Décisions et actions", "Le journal des décisions prises et à prendre, et les actions qui en découlent."),
    section("Décisions", "decision", lignes.filter(l => l.nature === "decision"), cols, recharger),
    section("Actions", "decision", lignes.filter(l => l.nature !== "decision"), cols, recharger));
}];

VUES.meteo = ["Météo hebdomadaire", PILOTAGE, async v => {
  const meteos = await api("GET", "meteo");
  if (!meteos.some(m => m.id === etat.meteo)) etat.meteo = meteos[0]?.id;
  const m = meteos.find(x => x.id === etat.meteo);
  v.append(titreVue("Météo hebdomadaire", "Le co-pilote assemble les chiffres et propose la rédaction. Vous relisez, tranchez et diffusez."));
  const menu = el("div", { class: "menu" },
    el("button", { class: "principal", onclick: e => pendant(e.target, "Rédaction en cours…", async () => {
      const r = await api("POST", "meteo"); etat.meteo = r.meteo.id;
      dire(r.avertissement || "Projet de météo généré.", !!r.avertissement); await recharger();
    }) }, "Générer la météo de la semaine"),
    meteos.map(x => el("button", { "aria-current": x.id === etat.meteo, onclick: () => { etat.meteo = x.id; etat.edition = false; recharger(); } },
      x.semaine, el("small", {}, `${x.statut} · rédaction : ${x.source}`))));
  const droite = el("div", {});
  if (!m) droite.append(el("div", { class: "vide" }, "Aucune météo générée."));
  else {
    const choix = el("select", { style: "width:auto" }, ["vert", "orange", "rouge"].map(t =>
      el("option", { value: t, selected: t === m.tendance }, LIB_TENDANCE[t])));
    const motif = el("input", { placeholder: "Motif, requis si la tendance diffère de la tendance calculée" });
    motif.value = m.motif_derogation || "";
    const edition = el("textarea", { id: "edition" }); edition.value = m.contenu;
    const enregistrer = (plus = {}) => api("PUT", `meteo/${m.id}`, {
      tendance: choix.value, motif_derogation: motif.value, ...(etat.edition ? { contenu: edition.value } : {}), ...plus });
    droite.append(
      m.source === "gabarit" && el("div", { class: "bandeau" }, "Météo factuelle, sans rédaction par le modèle : les impacts et les actions des points de vigilance restent à écrire."),
      el("div", { class: "carte" },
        el("div", { class: "barre", style: "margin-top:0" }, "Tendance calculée :", tendance(m.tendance_calculee),
          el("span", {}, "· Tendance retenue :"), choix),
        motif,
        el("div", { class: "barre", style: "margin-bottom:0" },
          el("button", { onclick: () => { etat.edition = !etat.edition; recharger(); } }, etat.edition ? "Aperçu" : "Modifier le texte"),
          el("button", { class: "principal", onclick: e => pendant(e.target, "…", async () => { await enregistrer(); etat.edition = false; dire("Météo enregistrée."); await recharger(); }) }, "Enregistrer"),
          el("button", { onclick: e => pendant(e.target, "Relecture en cours…", async () => {
            await enregistrer(); const r = await api("POST", `meteo/${m.id}/challenger`);
            dire(r.avertissement || "Relecture terminée.", !!r.avertissement); etat.edition = false; await recharger();
          }) }, "Challenger"),
          el("span", { class: "pousse" }),
          el("button", { onclick: () => telecharger(m) }, "Télécharger (.md)"),
          m.statut !== "diffusée" && el("button", { onclick: e => pendant(e.target, "…", async () => { await enregistrer({ statut: "diffusée" }); await recharger(); }) }, "Marquer comme diffusée"),
          el("button", { class: "danger", onclick: async () => {
            if (!confirm("Supprimer cette météo ?")) return;
            try { await api("DELETE", `meteo/${m.id}`); await recharger(); } catch (err) { dire(err.message, true); }
          } }, "Supprimer"))));
    const remarques = JSON.parse(m.remarques || "[]");
    if (remarques.length) droite.append(el("h3", {}, `Remarques du co-pilote (${remarques.length})`),
      el("div", { class: "liste" }, remarques.map(r => el("div", { class: "item" },
        el("div", { class: "tete" }, pastille(r.gravite === "haute" ? "rouge" : r.gravite === "moyenne" ? "orange" : "neutre", "Gravité " + r.gravite),
          pastille("neutre", r.origine === "règle" ? "Règle" : "Modèle"), el("span", { class: "titre" }, r.constat)),
        el("div", { class: "detail" }, r.suggestion)))));
    droite.append(el("h3", {}, etat.edition ? "Texte (Markdown)" : "Aperçu"),
      etat.edition ? edition : el("div", { class: "rendu" }, rendu(m.contenu)));
  }
  v.append(el("div", { class: "deux" }, menu, droite));
}];

// ---------- saisie ----------
VUES.sprints = ["Sprints", SAISIE, async v => {
  const sprints = await api("GET", "sprint");
  v.append(titreVue("Saisie des sprints", "Chiffres relevés en fin de sprint. Ils alimentent les indicateurs, l'atterrissage et les déclencheurs."),
    section("Historique", "sprint", sprints, [
      ["Sprint", l => l.numero, "num"], ["Fin", l => dateFr(l.date_fin)],
      ["Prévu", l => nb(l.prevu), "num"], ["Réalisé", l => nb(l.realise), "num"],
      ["Taux", l => (l.prevu > 0 ? pct(l.realise / l.prevu) : "—"), "num"],
      ["Ajouté", l => nb(l.ajoute), "num"], ["Reste", l => nb(l.reste), "num"],
      ["Anomalies créées / corrigées", l => `${nb(l.anomalies_creees)} / ${nb(l.anomalies_corrigees)}`, "num"],
      ["Moral", l => (l.moral ? l.moral + " / 5" : "—"), "num"]], recharger));
}];

VUES.cr = ["Comptes rendus", SAISIE, async v => {
  const [crs, props] = await Promise.all([api("GET", "compte_rendu"), api("GET", "proposition")]);
  if (!crs.some(c => c.id === etat.cr)) etat.cr = crs[0]?.id;
  const cr = crs.find(c => c.id === etat.cr);
  v.append(titreVue("Comptes rendus", "Déposez un compte rendu ou des notes : le co-pilote propose les mises à jour du registre, chacune avec l'extrait qui la justifie. Rien n'entre au registre sans votre validation."));
  const menu = el("div", { class: "menu" },
    el("button", { class: "principal", onclick: () => formulaire("compte_rendu", null, recharger) }, "Ajouter un compte rendu"),
    crs.map(c => el("button", { "aria-current": c.id === etat.cr, onclick: () => { etat.cr = c.id; recharger(); } },
      c.titre || "Sans titre", el("small", {}, dateFr(c.date) + " · " +
        props.filter(p => p.cr_id === c.id && p.statut === "en attente").length + " à valider"))));
  const droite = el("div", {});
  if (!cr) droite.append(el("div", { class: "vide" }, "Aucun compte rendu."));
  else {
    const siennes = props.filter(p => p.cr_id === cr.id);
    droite.append(el("div", { class: "barre", style: "margin-top:0" },
      el("strong", {}, cr.titre || "Sans titre"), el("span", { style: "color:var(--doux)" }, dateFr(cr.date)),
      el("button", { class: "pousse", onclick: () => formulaire("compte_rendu", cr, recharger) }, "Modifier le texte"),
      el("button", { class: "principal", onclick: e => pendant(e.target, "Analyse en cours…", async () => {
        const r = await api("POST", `compte_rendu/${cr.id}/extraire`);
        dire(r.filter(p => p.statut === "en attente").length + " proposition(s) à valider."); await recharger();
      }) }, siennes.length ? "Relancer l'extraction" : "Extraire les propositions")));
    const LIB = { risque: "Risque", adherence: "Adhérence", decision: "Décision", action: "Action" };
    droite.append(siennes.length ? el("div", { class: "liste" }, siennes.map(p => {
      const c = JSON.parse(p.contenu), attente = p.statut === "en attente";
      const infos = [c.porteur && "Porteur : " + c.porteur, c.echeance && "Échéance : " + dateFr(c.echeance),
        c.probabilite ? `Probabilité ${c.probabilite} / 3` : null, c.impact ? `Impact ${c.impact} / 3` : null].filter(Boolean).join(" · ");
      const agir = (verbe, ok) => async e => pendant(e.target, "…", async () => {
        await api("POST", `proposition/${p.id}/${verbe}`); dire(ok); await recharger(); });
      return el("div", { class: "item" },
        el("div", { class: "tete" }, pastille("neutre", LIB[p.cible] || p.cible),
          pastille("neutre", p.operation === "creer" ? "Création" : "Mise à jour de n° " + p.ref_id),
          el("span", { class: "titre" }, c.titre),
          !attente && pastille(p.statut === "acceptée" ? "vert" : "neutre", p.statut)),
        c.description && el("div", { class: "detail" }, c.description),
        infos && el("div", { class: "detail" }, infos),
        el("blockquote", {}, p.extrait ? "« " + p.extrait + " »" : "Aucun extrait fourni.",
          !p.extrait_verifie && [" ", pastille("orange", "Extrait non retrouvé dans le texte")]),
        attente && el("div", { class: "actions" },
          el("button", { class: "principal", onclick: agir("accepter", "Ajouté au registre.") }, "Accepter"),
          el("button", { onclick: agir("rejeter", "Proposition rejetée.") }, "Rejeter")));
    })) : el("div", { class: "vide" }, "Pas encore de proposition pour ce compte rendu."));
  }
  v.append(el("div", { class: "deux" }, menu, droite));
}];

// Rendu Markdown minimal (titres, tableaux, listes, gras), sans innerHTML.
function enLigne(texte) {
  return texte.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map(t =>
    t.startsWith("**") ? el("strong", {}, t.slice(2, -2)) : t.startsWith("_") && t.endsWith("_") ? el("em", {}, t.slice(1, -1)) : t);
}
function rendu(md) {
  const out = [], lignes = md.split("\n");
  for (let i = 0; i < lignes.length; i++) {
    const l = lignes[i];
    if (!l.trim()) continue;
    const t = /^(#{1,3}) (.*)/.exec(l);
    if (t) { out.push(el("h" + t[1].length, {}, enLigne(t[2]))); continue; }
    if (l.startsWith("|")) {
      const rangs = [];
      while (i < lignes.length && lignes[i].startsWith("|")) rangs.push(lignes[i++].slice(1, -1).split("|").map(c => c.trim()));
      i--;
      const corps = rangs.filter((r, n) => n !== 1 || !r.every(c => /^-+$/.test(c)));
      out.push(el("table", {}, el("thead", {}, el("tr", {}, corps[0].map(c => el("th", {}, c)))),
        el("tbody", {}, corps.slice(1).map(r => el("tr", {}, r.map(c => el("td", {}, enLigne(c))))))));
      continue;
    }
    if (l.startsWith("- ")) {
      const items = [];
      while (i < lignes.length && lignes[i].startsWith("- ")) items.push(el("li", {}, enLigne(lignes[i++].slice(2))));
      i--; out.push(el("ul", {}, items)); continue;
    }
    out.push(el("p", {}, enLigne(l)));
  }
  return out;
}
function telecharger(m) {
  const a = el("a", { href: URL.createObjectURL(new Blob([m.contenu], { type: "text/markdown" })),
    download: "meteo-" + m.cree_le + ".md" });
  a.click(); URL.revokeObjectURL(a.href);
}

// ---------- Historique des modifications ----------
const ACTIONS_HIST = { creation: ["Création", "vert"], modification: ["Modification", "neutre"],
  suppression: ["Suppression", "rouge"], import: ["Import", "orange"] };
const NOMS_TABLES = { mission: "fiche mission", meteo: "météo", proposition: "proposition", journal: "historique" };
const nomTable = t => ENTITES[t]?.nom || NOMS_TABLES[t] || t;
const libelleChamp = (t, k) => (ENTITES[t]?.champs.find(c => c[0] === k) || [k, k])[1];
const resume = l => (l ? l.titre || l.libelle || l.nom || l.activite || l.semaine || `n° ${l.id}` : "");
const court = v => { const s = v == null || v === "" ? "∅" : String(v); return s.length > 90 ? s.slice(0, 90) + "…" : s; };
VUES.historique = ["Historique", SAISIE, async v => {
  const filtre = etat.histoCible || "";
  const entrees = await api("GET", "journal?limite=300" + (filtre ? "&cible=" + filtre : ""));
  const choix = el("select", { style: "width:auto", "aria-label": "Type d'élément", onchange: e => { etat.histoCible = e.target.value; recharger(); } },
    el("option", { value: "" }, "Tous les éléments"),
    ["mission", ...Object.keys(ENTITES), "meteo", "proposition"].map(t => el("option", { value: t, selected: t === filtre }, nomTable(t))));
  v.append(titreVue("Historique des modifications",
    "Chaque création, modification et suppression, avec l'état avant et après. « Annuler » défait une modification si l'élément n'a pas changé depuis ; l'annulation est elle-même inscrite ici.", choix));
  if (!entrees.length) { v.append(el("div", { class: "vide" }, "Aucune modification enregistrée.")); return; }
  const parJour = new Map();
  for (const e of entrees) { const j = e.horodatage.slice(0, 10); if (!parJour.has(j)) parJour.set(j, []); parJour.get(j).push(e); }
  for (const [j, liste] of parJour) {
    v.append(el("h3", {}, dateFr(j)), el("div", { class: "liste" }, liste.map(e => {
      const [lib, classe] = ACTIONS_HIST[e.action] || [e.action, "neutre"];
      const diff = e.action === "modification"
        ? Object.keys(e.apres || {}).filter(k => JSON.stringify(e.apres[k]) !== JSON.stringify((e.avant || {})[k]))
        : [];
      return el("div", { class: "item", style: e.annule_par ? "opacity:.6" : null },
        el("div", { class: "tete" },
          el("span", { style: "color:var(--doux);font-variant-numeric:tabular-nums" }, e.horodatage.slice(11, 16)),
          pastille(classe, lib), el("span", {}, nomTable(e.cible)),
          el("span", { class: "titre" }, resume(e.apres || e.avant)),
          el("span", { class: "pousse", style: "margin-left:auto;color:var(--doux);font-size:13px" }, e.origine || ""),
          e.annule_par ? pastille("neutre", "Annulée")
            : ["creation", "modification", "suppression"].includes(e.action) && el("button", { onclick: async ev => {
                await pendant(ev.target, "…", async () => { await api("POST", `journal/${e.id}/annuler`); dire("Modification annulée."); await recharger(); });
              } }, "Annuler")),
        diff.length ? el("ul", { style: "margin:6px 0 0;padding-left:18px;font-size:13.5px;color:var(--doux)" },
          diff.map(k => el("li", {}, el("b", { style: "color:var(--texte)" }, libelleChamp(e.cible, k)), " : ",
            court(e.avant?.[k]), " → ", court(e.apres[k])))) : null);
    })));
  }
  if (entrees.length >= 300) v.append(el("p", { class: "aide", style: "margin-top:12px" }, "Seules les 300 dernières entrées sont affichées ; filtrez par type d'élément pour remonter plus loin."));
}];
