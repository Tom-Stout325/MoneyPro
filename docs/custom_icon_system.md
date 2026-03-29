# MoneyPro custom SVG icon system

This adds a reusable Airborne Images drone icon system that works similarly to Font Awesome, but uses your custom SVG logo.

## Files added
- `static/icons/airborne-drone.svg`
- `static/css/mp_icons.css`
- `templates/partials/icon.html`

## File updated
- `templates/index.html`

## Basic usage

### Font Awesome style
```html
<i class="mp-icon mp-icon-drone mp-icon-sm" aria-hidden="true"></i>
```

### With text
```html
<h5>
  <i class="mp-icon mp-icon-drone mp-icon-md mp-icon-pop"></i>
  Invoice Review
</h5>
```

### In a button
```html
<a class="btn btn-primary" href="#">
  <i class="mp-icon mp-icon-drone mp-icon-sm"></i>
  New Flight
</a>
```

### Using the reusable partial
```django
{% include "partials/icon.html" with name="drone" size="lg" class="me-2 mp-icon-pop" %}
```

### Wrapped icon styles
```django
{% include "partials/icon.html" with name="drone" size="md" wrapper="soft" class="me-2" %}
{% include "partials/icon.html" with name="drone" size="md" wrapper="circle" class="me-2" %}
{% include "partials/icon.html" with name="drone" size="md" wrapper="tile" class="me-2" %}
```

## Available icon names
All of these point to the Airborne Images drone SVG:
- `mp-icon-drone`
- `mp-icon-airborne`
- `mp-icon-brand`
- `mp-icon-logo`

## Available sizes
- `mp-icon-xs`
- `mp-icon-sm`
- `mp-icon-md`
- `mp-icon-lg`
- `mp-icon-xl`
- `mp-icon-2xl`
- `mp-icon-3xl`
- `mp-icon-4xl`

## Suggested uses in MoneyPro
- dashboard cards
- invoice action headers
- report section titles
- navbar brand accents
- empty states
- quick action buttons

## Example section heading
```html
<div class="d-flex align-items-center gap-2 mb-3">
  <span class="mp-icon-soft">
    <i class="mp-icon mp-icon-drone mp-icon-md"></i>
  </span>
  <div>
    <h2 class="h5 mb-0">Associated transactions</h2>
    <p class="text-muted small mb-0">Linked by invoice number</p>
  </div>
</div>
```
