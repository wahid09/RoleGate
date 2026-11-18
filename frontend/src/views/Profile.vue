<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'
import { passwordStrength } from '../utils/password'
import UserAvatar from '../components/UserAvatar.vue'
import TwoFactorCard from '../components/TwoFactorCard.vue'
import PasskeysCard from '../components/PasskeysCard.vue'
import SessionsCard from '../components/SessionsCard.vue'

const auth = useAuth()

const TABS = [
  { id: 'account', label: 'Account', icon: 'bi-person' },
  { id: 'security', label: 'Security', icon: 'bi-shield-lock' },
  { id: 'devices', label: 'Devices', icon: 'bi-laptop' },
]
const tab = ref('account')
onMounted(() => {
  const h = window.location.hash.slice(1)
  if (TABS.some((t) => t.id === h)) tab.value = h
})
function select(id) {
  tab.value = id
  try {
    history.replaceState(null, '', `#${id}`)
  } catch {
    /* hash is only a convenience */
  }
}

// ---- change password ----
const form = ref({ current_password: '', new_password: '', confirm: '' })
const error = ref('')
const success = ref('')
const loading = ref(false)
const reveal = ref(false)

const strength = computed(() => passwordStrength(form.value.new_password))
const mismatch = computed(() => form.value.confirm.length > 0 && form.value.confirm !== form.value.new_password)

async function submit() {
  error.value = ''
  success.value = ''
  if (form.value.new_password !== form.value.confirm) {
    error.value = 'New passwords do not match'
    return
  }
  loading.value = true
  try {
    const { data } = await http.post('/auth/change-password', {
      current_password: form.value.current_password,
      new_password: form.value.new_password,
    })
    success.value = data.message
    form.value = { current_password: '', new_password: '', confirm: '' }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

// ---- permissions, grouped by resource ----
const permGroups = computed(() => {
  const map = new Map()
  for (const p of auth.user?.permissions || []) {
    const [res, ...rest] = p.split(':')
    if (!map.has(res)) map.set(res, [])
    map.get(res).push(rest.join(':'))
  }
  return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
})
const permCount = computed(() => auth.user?.permissions?.length || 0)
const showAllPerms = ref(false)
const visiblePerms = computed(() => (showAllPerms.value ? permGroups.value : permGroups.value.slice(0, 4)))
</script>

<template>
  <div class="w-auto profile-page">
    <!-- identity header -->
    <section class="hero">
      <UserAvatar :name="auth.user?.full_name" :email="auth.user?.email" :size="72" />
      <div class="hero-main">
        <h4 class="mb-1">{{ auth.user?.full_name || auth.user?.email }}</h4>
        <div class="hero-email">
          {{ auth.user?.email }}
          <span v-if="auth.user?.email_verified" class="chip chip-ok">
            <i class="bi bi-patch-check-fill" aria-hidden="true"></i> Verified
          </span>
          <span v-else class="chip chip-warn">Not verified</span>
        </div>
        <div class="hero-roles">
          <span v-for="r in auth.user?.roles" :key="r.id" class="pill">{{ r.name }}</span>
          <span v-if="!auth.user?.roles?.length" class="text-muted small">No roles assigned</span>
        </div>
      </div>
      <div class="hero-sec" :class="auth.user?.mfa_enabled ? 'on' : 'off'">
        <i class="bi" :class="auth.user?.mfa_enabled ? 'bi-shield-check' : 'bi-shield-exclamation'" aria-hidden="true"></i>
        <div>
          <div class="fw-semibold">{{ auth.user?.mfa_enabled ? 'Two-step sign-in is on' : 'Two-step sign-in is off' }}</div>
          <button v-if="!auth.user?.mfa_enabled" class="btn-link-plain" @click="select('security')">Turn it on</button>
          <span v-else class="small text-muted">Your account has extra protection</span>
        </div>
      </div>
    </section>

    <!-- tabs -->
    <div class="tabs" role="tablist" aria-label="Profile sections">
      <button v-for="t in TABS" :id="`tab-${t.id}`" :key="t.id" role="tab" type="button" class="tab"
              :class="{ on: tab === t.id }" :aria-selected="tab === t.id" :aria-controls="`panel-${t.id}`"
              @click="select(t.id)">
        <i class="bi" :class="t.icon" aria-hidden="true"></i> {{ t.label }}
      </button>
    </div>

    <!-- account -->
    <div v-show="tab === 'account'" id="panel-account" role="tabpanel" aria-labelledby="tab-account" class="grid">
      <section class="panel">
        <header class="panel-head"><i class="bi bi-person-vcard" aria-hidden="true"></i> Your details</header>
        <dl class="details">
          <div><dt>Name</dt><dd>{{ auth.user?.full_name || '—' }}</dd></div>
          <div><dt>Email</dt><dd>{{ auth.user?.email }}</dd></div>
          <div>
            <dt>Roles</dt>
            <dd>
              <span v-for="r in auth.user?.roles" :key="r.id" class="pill">{{ r.name }}</span>
              <span v-if="!auth.user?.roles?.length" class="text-muted">None</span>
            </dd>
          </div>
        </dl>
        <header class="panel-head sub">
          <i class="bi bi-key" aria-hidden="true"></i> What you can do
          <span class="count">{{ permCount }}</span>
        </header>
        <div class="perms">
          <p v-if="!permCount" class="text-muted small mb-0">You have no permissions yet. Ask an administrator for access.</p>
          <div v-for="[res, acts] in visiblePerms" :key="res" class="perm-row">
            <span class="perm-res">{{ res }}</span>
            <span class="perm-acts"><span v-for="a in acts" :key="a" class="act">{{ a }}</span></span>
          </div>
          <button v-if="permGroups.length > 4" type="button" class="btn-link-plain mt-2" @click="showAllPerms = !showAllPerms">
            {{ showAllPerms ? 'Show fewer' : `Show all ${permGroups.length} areas` }}
          </button>
        </div>
      </section>

      <section class="panel">
        <header class="panel-head"><i class="bi bi-key" aria-hidden="true"></i> Change password</header>
        <form class="panel-body" @submit.prevent="submit">
          <div v-if="error" class="alert alert-danger py-2" role="alert">{{ error }}</div>
          <div v-if="success" class="alert alert-success py-2" role="status">{{ success }}</div>

          <div class="mb-3">
            <label class="form-label" for="pw-current">Current password</label>
            <input id="pw-current" v-model="form.current_password" :type="reveal ? 'text' : 'password'"
                   class="form-control" required autocomplete="current-password" />
          </div>
          <div class="mb-3">
            <label class="form-label" for="pw-new">New password</label>
            <input id="pw-new" v-model="form.new_password" :type="reveal ? 'text' : 'password'" class="form-control"
                   required minlength="8" autocomplete="new-password" aria-describedby="pw-hint" />
            <div v-if="form.new_password" class="meter" aria-hidden="true">
              <span v-for="n in 4" :key="n" class="seg" :class="[n <= strength.score ? `s${strength.score}` : '']"></span>
            </div>
            <div id="pw-hint" class="form-text" aria-live="polite">
              <template v-if="form.new_password">Strength: <strong>{{ strength.label }}</strong></template>
              <template v-else>At least 8 characters. A longer phrase is stronger.</template>
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label" for="pw-confirm">Confirm new password</label>
            <input id="pw-confirm" v-model="form.confirm" :type="reveal ? 'text' : 'password'" class="form-control"
                   :class="{ 'is-invalid': mismatch }" required autocomplete="new-password" />
            <div v-if="mismatch" class="invalid-feedback">Passwords do not match</div>
          </div>
          <div class="form-check mb-3">
            <input id="pw-reveal" v-model="reveal" type="checkbox" class="form-check-input" />
            <label class="form-check-label small" for="pw-reveal">Show passwords</label>
          </div>
          <button class="btn btn-primary" :disabled="loading || mismatch">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Update password
          </button>
        </form>
      </section>
    </div>

    <!-- security -->
    <div v-show="tab === 'security'" id="panel-security" role="tabpanel" aria-labelledby="tab-security" class="stack cards">
      <TwoFactorCard />
      <PasskeysCard />
    </div>

    <!-- devices -->
    <div v-show="tab === 'devices'" id="panel-devices" role="tabpanel" aria-labelledby="tab-devices" class="stack cards">
      <SessionsCard />
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  --radius: 12px;
  max-width: 1040px;
}
.hero {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  padding: 1.5rem;
  margin-bottom: 1.25rem;
  background: var(--bs-body-bg);
  border: 1px solid var(--bs-border-color);
  border-radius: var(--radius);
  box-shadow: 0 1px 2px rgb(16 24 40 / 0.04);
}
.hero-main {
  flex: 1;
  min-width: 0;
}
.hero-email {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  color: var(--bs-secondary-color);
  margin-bottom: 0.6rem;
  overflow-wrap: anywhere;
}
.hero-sec {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  font-size: 0.875rem;
}
.hero-sec .bi {
  font-size: 1.5rem;
}
.hero-sec.on {
  background: var(--bs-success-bg-subtle);
  color: var(--bs-success-text-emphasis);
}
.hero-sec.off {
  background: var(--bs-warning-bg-subtle);
  color: var(--bs-warning-text-emphasis);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 999px;
}
.chip-ok {
  background: var(--bs-success-bg-subtle);
  color: var(--bs-success-text-emphasis);
}
.chip-warn {
  background: var(--bs-warning-bg-subtle);
  color: var(--bs-warning-text-emphasis);
}
.pill {
  display: inline-block;
  margin: 0 0.3rem 0.2rem 0;
  padding: 0.15rem 0.65rem;
  font-size: 0.8125rem;
  border-radius: 999px;
  background: var(--bs-secondary-bg);
  color: var(--bs-body-color);
}
.btn-link-plain {
  border: 0;
  background: none;
  padding: 0;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--bs-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* tabs */
.tabs {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  margin-bottom: 1.25rem;
  background: var(--bs-tertiary-bg);
  border-radius: 10px;
  max-width: 100%;
  overflow-x: auto;
}
.tab {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 1rem;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font-size: 0.9rem;
  white-space: nowrap;
  color: var(--bs-secondary-color);
  transition: background-color 0.15s, color 0.15s;
}
.tab:hover {
  color: var(--bs-body-color);
}
.tab.on {
  background: var(--bs-body-bg);
  color: var(--bs-body-color);
  font-weight: 600;
  box-shadow: 0 1px 2px rgb(16 24 40 / 0.12);
}

/* layout */
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}
.stack {
  display: grid;
  gap: 1.25rem;
  max-width: 720px;
}
.panel {
  background: var(--bs-body-bg);
  border: 1px solid var(--bs-border-color);
  border-radius: var(--radius);
  box-shadow: 0 1px 2px rgb(16 24 40 / 0.04);
  overflow: hidden;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.85rem 1.25rem;
  font-weight: 600;
  border-bottom: 1px solid var(--bs-border-color);
  background: var(--bs-tertiary-bg);
}
.panel-head.sub {
  border-top: 1px solid var(--bs-border-color);
}
.count {
  padding: 0.05rem 0.5rem;
  font-size: 0.75rem;
  border-radius: 999px;
  background: var(--bs-secondary-bg);
  color: var(--bs-secondary-color);
}
.panel-body {
  padding: 1.25rem;
}
.details {
  margin: 0;
}
.details > div {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 0.5rem;
  padding: 0.7rem 1.25rem;
  border-bottom: 1px solid var(--bs-border-color-translucent);
}
.details > div:last-child {
  border-bottom: 0;
}
.details dt {
  font-weight: 500;
  color: var(--bs-secondary-color);
}
.details dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.perms {
  padding: 0.5rem 1.25rem 1.1rem;
}
.perm-row {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 0.5rem;
  padding: 0.4rem 0;
}
.perm-res {
  font-weight: 600;
  font-size: 0.875rem;
}
.act {
  display: inline-block;
  margin: 0 0.3rem 0.25rem 0;
  padding: 0.05rem 0.5rem;
  font-family: var(--bs-font-monospace);
  font-size: 0.75rem;
  border-radius: 6px;
  background: var(--bs-primary-bg-subtle);
  color: var(--bs-primary-text-emphasis);
}

/* password strength */
.meter {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  margin-top: 0.5rem;
}
.seg {
  height: 4px;
  border-radius: 2px;
  background: var(--bs-secondary-bg);
}
.seg.s1 {
  background: var(--bs-danger);
}
.seg.s2 {
  background: var(--bs-warning);
}
.seg.s3,
.seg.s4 {
  background: var(--bs-success);
}

/* make the existing cards (2FA, passkeys, sessions) match the new panels */
.cards :deep(.card) {
  border: 1px solid var(--bs-border-color) !important;
  border-radius: var(--radius);
  box-shadow: 0 1px 2px rgb(16 24 40 / 0.04) !important;
  overflow: hidden;
  margin-bottom: 0 !important;
}
.cards :deep(.card-header) {
  background: var(--bs-tertiary-bg) !important;
  border-bottom: 1px solid var(--bs-border-color);
  padding: 0.85rem 1.25rem;
}
.cards :deep(.card-body) {
  padding: 1.25rem;
}

@media (max-width: 991.98px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 575.98px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
    padding: 1.25rem;
  }
  .hero-sec {
    width: 100%;
  }
  .tabs {
    display: flex;
  }
  .tab {
    flex: 1;
    justify-content: center;
    padding: 0.45rem 0.5rem;
  }
  .details > div,
  .perm-row {
    grid-template-columns: 1fr;
    gap: 0.1rem;
  }
}
@media (prefers-reduced-motion: reduce) {
  .tab {
    transition: none;
  }
}
</style>
