const selector = document.querySelector('#product_id');
function updatePreview() {
  const option = selector?.selectedOptions[0];
  const preview = document.querySelector('#stock-preview');
  if (!preview) return;
  preview.textContent = option?.value
    ? `Disponible: ${option.dataset.stock} ${option.dataset.unit} · ${option.dataset.location}`
    : 'Seleccioná un insumo para consultar su disponibilidad.';
  const amount = document.querySelector('#amount');
  if (amount && option?.value) {
    amount.step = option.dataset.unit === 'unidad' ? '1' : '0.001';
    amount.min = amount.step;
  }
}
selector?.addEventListener('change', updatePreview);
updatePreview();

for (const button of document.querySelectorAll('[data-open-dialog]')) {
  button.addEventListener('click', () => {
    document.getElementById(button.dataset.openDialog)?.showModal();
  });
}
for (const button of document.querySelectorAll('[data-close-dialog]')) {
  button.addEventListener('click', () => button.closest('dialog').close());
}
for (const time of document.querySelectorAll('time[datetime]')) {
  const date = new Date(time.dateTime);
  if (!Number.isNaN(date.getTime())) {
    time.textContent = new Intl.DateTimeFormat('es-AR', {
      dateStyle: 'medium', timeStyle: 'short', timeZoneName: undefined,
    }).format(date);
  }
}
document.querySelector('[data-dismiss-alert]')?.addEventListener('click', event => {
  event.currentTarget.closest('.stock-notification').remove();
});
