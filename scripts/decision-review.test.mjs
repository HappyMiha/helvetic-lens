import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderLocalizedComponent } from "./analysis-mode-fixtures.mjs";

const source = {version_id:"old",passage_id:"p1",quote:"Proposed amendment — source remains unchanged.",url:"/evidence/old?passage=p1"};
for(const locale of ["en-CH","de-CH","fr-CH","it-CH","rm-CH"]) {
  for(const basis of ["saved_comparison", "model_interpretation", undefined]) {
    test(`each change exposes its explanation basis in ${locale}/${basis}`, () => {
      const html=renderLocalizedComponent("decision-review.tsx", "ChangeExplanationBasis", locale, {basis});
      if(!basis) assert.equal(html, "");
      else assert.match(html, new RegExp(`data-explanation-basis="${basis}"`));
    });
  }
  for(const state of ["review_actions","no_action_now","not_reviewed","legacy","selected_evidence"]) {
    test(`decision report distinguishes review and absence in ${locale}/${state}`, () => {
      const report = {response_mode: state === "selected_evidence" ? state : "generated_explanation",actions:[],
        decision_review: state === "legacy" ? undefined : {basis:"model_interpretation",explained_changes:1,available_changes:2},
        evidence_coverage:{material_items:12},organization_applicability:{conditions:["Only covered synthetic records."]},
        official_status:{status:"proposal",explanation:"Synthetic status interpretation.",citations:[source]},
        action_review:{status:state,explanation:"Synthetic action reasoning.",citations:[source]}};
      const props={report, renderCitations: (values) => createElement("nav",null,...values.map(c=>createElement("a",{href:c.url,key:c.url},c.quote)))};
      const decision=renderLocalizedComponent("decision-review.tsx","DecisionReview",locale,props);
      if(state === "selected_evidence") { assert.equal(decision,""); return; }
      const action=renderLocalizedComponent("decision-review.tsx","ActionReviewNotice",locale,props);
      assert.doesNotMatch(decision+action,/\{explained\}|\{total\}|undefined/);
      if(state === "legacy") {
        assert.match(decision,/data-decision-review="legacy"/);
        assert.doesNotMatch(decision,/data-official-status/);
        assert.match(action,/data-action-review="not_reviewed"/);
        assert.doesNotMatch(action,/Synthetic action reasoning/);
      } else {
        assert.match(decision,/data-official-status="proposal"/);
        assert.match(decision,/12/);
        assert.match(decision,/Only covered synthetic records/);
        assert.match(decision,/Proposed amendment — source remains unchanged/);
        assert.match(action,new RegExp(`data-action-review="${state}"`));
        assert.match(action,/Synthetic action reasoning/);
        assert.match(action,/href="\/evidence\/old\?passage=p1"/);
      }
    });
  }
}
