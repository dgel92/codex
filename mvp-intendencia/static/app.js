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
