// Update one saved decision without rebuilding the avatar, microphone or SBAR form.
export function applyDecisionResult(form, result) {
  const x=window.scrollX,y=window.scrollY;
  form.querySelectorAll('input[type="radio"]').forEach(input => { input.disabled = true; });
  const feedback = document.createElement('div');
  feedback.className = 'note';
  feedback.dataset.decisionFeedback = 'saved';
  feedback.setAttribute('role', 'status');
  feedback.tabIndex = -1;
  feedback.textContent = `${result.score} / ${result.max_score} 分 · ${result.feedback}`;
  const actions = form.querySelector('.actions');
  if (actions) actions.replaceChildren(feedback);
  form.dataset.saved = 'true';
  feedback.focus({preventScroll: true});
  window.scrollTo(x,y);
}
