<template>
  <TitleBar icon="fa:download">{{ t('action:deploy-xoa') }}</TitleBar>
  <div v-if="deploying" class="status">
    <img src="@/assets/xo.svg" width="300" alt="Xen Orchestra" />

    <!-- Error -->
    <template v-if="error !== undefined">
      <div>
        <h2>{{ t('xoa-deploy-failed!') }}</h2>
        <VtsIcon name="status:danger-circle" size="medium" />
      </div>
      <div class="error">
        <strong>{{ t('check-errors:') }}</strong>
        <UiRaw>{{ error }}</UiRaw>
      </div>
      <UiButton size="medium" accent="brand" variant="primary" left-icon="fa:download" @click="resetValues()">
        {{ t('xoa-deploy-retry') }}
      </UiButton>
    </template>

    <!-- Success -->
    <template v-else-if="url !== undefined">
      <div>
        <h2>{{ t('xoa-deploy-successful!') }}</h2>
        <VtsIcon name="status:success-circle" size="medium" />
      </div>
      <UiButton
        size="medium"
        accent="brand"
        variant="primary"
        left-icon="fa:arrow-up-right-from-square"
        @click="openXoa"
      >
        {{ t('access-xoa') }}
      </UiButton>
    </template>

    <!-- Deploying -->
    <template v-else>
      <div>
        <h2>{{ t('xoa-deploy') }}</h2>
        <!-- TODO: add progress bar -->
        <p>{{ status }}</p>
      </div>
      <p class="warning">
        <VtsIcon name="status:warning-circle" size="medium" />
        {{ t('keep-page-open') }}
      </p>
      <UiButton size="medium" :disabled="vmRef === undefined" accent="danger" variant="secondary" @click="cancel()">
        {{ t('cancel') }}
      </UiButton>
    </template>
  </div>

  <div v-else-if="uiStore.isSmall" class="not-available">
    <p>{{ t('deploy-xoa-available-on-desktop') }}</p>
  </div>

  <div v-else class="card-view">
    <UiCard>
      <form @submit.prevent="deploy">
        <FormSection :label="t('configuration')">
          <!-- Image source selector -->
          <div class="row">
            <VtsInputWrapper :label="t('xoa-image-url')">
              <div class="image-source-row">
                <select v-model="imageSource" class="image-source-select">
                  <option value="vates">{{ t('vates-image') }}</option>
                  <option value="ronivay">{{ t('ronivay-image') }}</option>
                  <option value="custom">{{ t('custom-url') }}</option>
                </select>
                <FormInput
                  v-if="imageSource === 'custom'"
                  v-model="xoaImageUrl"
                  placeholder="https://example.com/image.xva.gz"
                  class="custom-url-input"
                />
              </div>
            </VtsInputWrapper>
          </div>
          <!-- SSL toggle: only relevant for proxy paths (ronivay / custom) -->
          <div v-if="imageSource !== 'vates'" class="row">
            <VtsInputWrapper>
              <UiToggle v-model="verifySsl">{{ t('verify-ssl-certificate') }}</UiToggle>
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper :label="t('storage')" :message="t('n-gb-required', { n: REQUIRED_GB })">
              <VtsSelect :id="srSelectId" accent="brand" />
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper :label="t('network')">
              <VtsSelect :id="networkSelectId" accent="brand" />
            </VtsInputWrapper>
            <VtsInputWrapper :label="t('deploy-xoa-custom-ntp-servers')" learn-more-url="https://docs.xen-orchestra.com/xoa#setting-a-custom-ntp-server">
              <FormInput v-model="ntp" placeholder="xxx.xxx.xxx.xxx" />
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper>
              <UiRadioButtonGroup accent="brand" gap="wide">
                <UiRadioButton v-model="ipStrategy" accent="brand" value="static">
                  {{ t('static-ip') }}
                </UiRadioButton>
                <UiRadioButton v-model="ipStrategy" accent="brand" value="dhcp">
                  {{ t('dhcp') }}
                </UiRadioButton>
              </UiRadioButtonGroup>
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper
              :label="t('xoa-ip')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#network-configuration"
            >
              <FormInput v-model="ip" :disabled="!requireIpConf" placeholder="xxx.xxx.xxx.xxx" />
            </VtsInputWrapper>
            <VtsInputWrapper
              :label="t('netmask')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#network-configuration"
            >
              <FormInput v-model="netmask" :disabled="!requireIpConf" placeholder="255.255.255.0" />
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper
              :label="t('dns')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#network-configuration"
            >
              <FormInput v-model="dns" :disabled="!requireIpConf" placeholder="8.8.8.8" />
            </VtsInputWrapper>
            <VtsInputWrapper
              :label="t('gateway')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#network-configuration"
            >
              <FormInput v-model="gateway" :disabled="!requireIpConf" placeholder="xxx.xxx.xxx.xxx" />
            </VtsInputWrapper>
          </div>
        </FormSection>

        <FormSection :label="t('xoa-admin-account')">
          <div class="row">
            <VtsInputWrapper
              :label="t('admin-login')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#default-xo-account"
            >
              <FormInput
                v-model="xoaUser"
                :disabled="!isEditable"
                :required="isEditable"
                :placeholder="isEditable ? 'email@example.com' : 'admin@admin.net'"
              />
              <FormInput value="admin@admin.net" placeholder="admin@admin.net" disabled />
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper
              :label="t('admin-password')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#default-xo-account"
            >
              <FormInput
                v-model="xoaPwd"
                :type="isEditable ? 'password' : 'text'"
                :disabled="!isEditable"
                :required="isEditable"
                :placeholder="isEditable ? t('password') : 'admin'"
              />
              <FormInput value="admin" placeholder="admin" disabled />
            </VtsInputWrapper>
            <VtsInputWrapper
              :label="t('admin-password-confirm')"
              learn-more-url="https://docs.xen-orchestra.com/xoa#default-xo-account"
            >
              <FormInput
                v-model="xoaPwdConfirm"
                :type="isEditable ? 'password' : 'text'"
                :disabled="!isEditable"
                :required="isEditable"
                :placeholder="isEditable ? t('password') : 'admin'"
              />
              <FormInput value="admin" placeholder="admin" disabled />
            </VtsInputWrapper>
          </div>
        </FormSection>

        <FormSection :label="t('xoa-ssh-account')">
          <div class="row">
            <UiToggle v-model="enableSshAccount" :disabled="!isEditable">{{ t('ssh-account') }}</UiToggle>
          </div>
          <div class="row">
            <VtsInputWrapper :label="t('ssh-login')">
              <FormInput value="xo" placeholder="xo" disabled />
            </VtsInputWrapper>
          </div>
          <div class="row">
            <VtsInputWrapper :label="t('ssh-password')">
              <FormInput
                v-model="sshPwd"
                :type="isEditable ? 'password' : 'text'"
                :placeholder="isEditable ? t('password') : 'xopass'"
                :disabled="!isEditable || !enableSshAccount"
                :required="isEditable && enableSshAccount"
              />
            </VtsInputWrapper>
            <VtsInputWrapper :label="t('ssh-password-confirm')">
              <FormInput
                v-model="sshPwdConfirm"
                :type="isEditable ? 'password' : 'text'"
                :placeholder="isEditable ? t('password') : 'xopass'"
                :disabled="!isEditable || !enableSshAccount"
                :required="isEditable && enableSshAccount"
              />
              <FormInput value="xopass" placeholder="xopass" disabled />
            </VtsInputWrapper>
            <VtsInputWrapper :label="t('ssh-password-confirm')">
              <FormInput value="xopass" placeholder="xopass" disabled />
            </VtsInputWrapper>
          </div>
        </FormSection>

        <VtsButtonGroup>
          <UiButton size="medium" accent="brand" variant="secondary" @click="router.back()">
            {{ t('cancel') }}
          </UiButton>
          <UiButton size="medium" accent="brand" variant="primary" type="submit">
            {{ t('action:deploy') }}
          </UiButton>
        </VtsButtonGroup>
      </form>
    </UiCard>
  </div>
</template>

<script lang="ts" setup>
import FormInput from '@/components/form/FormInput.vue'
import FormSection from '@/components/form/FormSection.vue'
import TitleBar from '@/components/TitleBar.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiRaw from '@/components/ui/UiRaw.vue'
import { usePageTitleStore } from '@/stores/page-title.store'
import { useNetworkStore } from '@/stores/xen-api/network.store'
import { useSrStore } from '@/stores/xen-api/sr.store'
import { useXenApiStore } from '@/stores/xen-api.store'
import VtsButtonGroup from '@core/components/button-group/VtsButtonGroup.vue'
import VtsIcon from '@core/components/icon/VtsIcon.vue'
import VtsInputWrapper from '@core/components/input-wrapper/VtsInputWrapper.vue'
import VtsSelect from '@core/components/select/VtsSelect.vue'
import UiButton from '@core/components/ui/button/UiButton.vue'
import UiRadioButton from '@core/components/ui/radio-button/UiRadioButton.vue'
import UiRadioButtonGroup from '@core/components/ui/radio-button-group/UiRadioButtonGroup.vue'
import UiToggle from '@core/components/ui/toggle/UiToggle.vue'
import { useFormSelect } from '@core/packages/form-select'
import { useModal } from '@core/packages/modal/use-modal.ts'
import { useUiStore } from '@core/stores/ui.store'
import { logicNot } from '@vueuse/math'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const REQUIRED_GB = 20

// ── XOA image sources ─────────────────────────────────────────────────────────
// Option 1 – Vates official: VM.import called directly, no proxy.
// Option 2 – Ronivay community: routed through xoa-proxy (gzip + HTTP/HTTPS).
// Option 3 – Custom URL: same proxy path as ronivay.
const XOA_VATES_IMAGE_URL = 'http://xoa.io/xva'
const XOA_RONIVAY_IMAGE_URL = 'https://xo-image.yawn.fi/downloads/image.xva.gz'

type ImageSource = 'vates' | 'ronivay' | 'custom'

/** Which image source is currently selected. */
const imageSource = ref<ImageSource>('ronivay')

/**
 * User-entered URL, only used when imageSource === 'custom'.
 * The proxy auto-detects gzip vs raw XVA from the URL extension.
 */
const xoaImageUrl = ref('')

// ── Proxy config ──────────────────────────────────────────────────────────────
// XOA_PROXY_PORT must match the port xoa-proxy is listening on (default 9001).
const XOA_PROXY_PORT = 9001
const XOA_PROXY_BIND_ADDRESS = '127.0.0.1'

/**
 * When true (default), xoa-proxy verifies the upstream TLS certificate.
 * Uncheck only for self-signed / private-CA image servers.
 * Not applicable for the Vates path (no proxy used).
 */
const verifySsl = ref(true)

/**
 * Builds the local proxy URL that VM.import will pull from.
 *
 * Handles all four combinations transparently:
 *   http  + .xva     → relay HTTP → HTTP, stream raw
 *   http  + .xva.gz  → relay HTTP → HTTP, decompress gzip
 *   https + .xva     → relay HTTPS → HTTP, stream raw
 *   https + .xva.gz  → relay HTTPS → HTTP, decompress gzip
 */
function buildProxyUrl(sourceUrl: string, sslVerify: boolean): string {
  const params = new URLSearchParams({ src: sourceUrl })
  if (!sslVerify) {
    params.set('verify_ssl', 'false')
  }
  return `http://${XOA_PROXY_BIND_ADDRESS}:${XOA_PROXY_PORT}/image.xva?${params.toString()}`
// ── XOA image source & proxy ──────────────────────────────────────────────────
//
// The official XOA appliance image is distributed as a gzip-compressed XVA
// over HTTPS. XAPI's VM.import speaks only HTTP and expects an uncompressed
// stream, so we route through xoa-proxy.py running on Dom0.
//
// XOA_SOURCE_URL: update this to the current Vates download URL.
//   Format:  https://<host>/path/to/xoa-<version>.xva.gz
//   Obtain the signed URL from https://vates.tech/deploy/ if required.
//
// XOA_PROXY_PORT: must match the PORT constant in xoa-proxy.py (default 9001).
//   The proxy listens on 127.0.0.1 — reachable by XAPI on the same Dom0 host.
//
// VM.import receives: http://127.0.0.1:9001/image.xva?src=<encoded-source-url>
// xoa-proxy.py fetches the src URL via HTTPS, gunzips on-the-fly, streams back.
const XOA_SOURCE_URL = 'https://xoa.io/xoa-lts.xva.gz'
const XOA_PROXY_PORT = 9001

/** Builds the local proxy URL that VM.import will pull from. */
function buildProxyUrl(sourceUrl: string): string {
  return `http://127.0.0.1:${XOA_PROXY_PORT}/image.xva?src=${encodeURIComponent(sourceUrl)}`
}

const { t } = useI18n()
const router = useRouter()

usePageTitleStore().setTitle(() => t('action:deploy-xoa'))

const openInvalidFieldModal = useModal((message: string) => ({
  component: import('@/components/modals/InvalidFieldModal.vue'),
  props: { message },
}))

const uiStore = useUiStore()

const xapi = useXenApiStore().getXapi()

const { records: srs, isReady: isSrReady } = useSrStore().subscribe()
const filteredSrs = computed(() =>
  srs.value
    .filter(sr => sr.content_type !== 'iso' && sr.physical_size > 0)
    // Sort: shared first then largest free space first
    .sort((sr1, sr2) => {
      if (sr1.shared === sr2.shared) {
        return sr2.physical_size - sr2.physical_utilisation - (sr1.physical_size - sr1.physical_utilisation)
      } else {
        return sr1.shared ? -1 : 1
      }
    })
)

const { records: networks, isReady: isNetworkReady } = useNetworkStore().subscribe()
const filteredNetworks = computed(() =>
  [...networks.value].sort((network1, network2) => (network1.name_label < network2.name_label ? -1 : 1))
)

const deploying = ref(false)
const status = ref<string | undefined>()
const error = ref<string | undefined>()
const url = ref<string | undefined>()
const vmRef = ref<string | undefined>()

const resetValues = () => {
  deploying.value = false
  status.value = undefined
  error.value = undefined
  url.value = undefined
  vmRef.value = undefined
}

const openXoa = () => {
  window.open(url.value, '_blank', 'noopener')
}

// SR SELECTOR

const { id: srSelectId, selectedValue: selectedSr } = useFormSelect(filteredSrs, {
  loading: logicNot(isSrReady),
  placeholder: t('action:select-storage'),
  option: {
    properties: sr => {
      const spaceLeft = computed(() => sr.physical_size - sr.physical_utilisation)
      return {
        spaceLeft,
        accent: computed(() => (spaceLeft.value < REQUIRED_GB * 1024 ** 3 ? 'warning' : 'normal')),
      }
    },
    id: sr => sr.uuid,
    label: (sr, { spaceLeft }) => {
      const gbLeft = t('n-gb-left', { n: Math.round(spaceLeft.value / 1024 ** 3) })
      return `${sr.name_label} - ${gbLeft}`
    },
  },
})

// NETWORK SELECTOR

const { id: networkSelectId, selectedValue: selectedNetwork } = useFormSelect(filteredNetworks, {
  loading: logicNot(isNetworkReady),
  searchable: true,
  placeholder: t('action:select-network'),
  option: {
    id: 'uuid',
    label: 'name_label',
  },
})

const ntp = ref('')
const ipStrategy = ref<'static' | 'dhcp'>('dhcp')
const requireIpConf = computed(() => ipStrategy.value === 'static')

const ip = ref('')
const netmask = ref('')
const dns = ref('')
const gateway = ref('')

// Credential refs — values depend on imageSource (see watch below).
// Start with CE defaults because default imageSource is 'ronivay'.
const xoaUser = ref('admin@admin.net')
const xoaPwd = ref('admin')
const xoaPwdConfirm = ref('admin')
const enableSshAccount = ref(true)
const sshPwd = ref('xopass')
const sshPwdConfirm = ref('xopass')

/**
 * True when fields should be editable (Vates or Custom).
 * Only the Ronivay option uses baked-in, pre-filled credentials.
 */
const isEditable = computed(() => imageSource.value !== 'ronivay')

/**
 * When switching to the Vates path, clear baked-in defaults so the user must
 * fill in real credentials (upstream behaviour).
 * When switching away, restore the pre-filled CE defaults.
 */
watch(imageSource, source => {
  if (source === 'ronivay') {
    xoaUser.value = 'admin@admin.net'
    xoaPwd.value = 'admin'
    xoaPwdConfirm.value = 'admin'
    sshPwd.value = 'xopass'
    sshPwdConfirm.value = 'xopass'
    enableSshAccount.value = true
  } else {
    xoaUser.value = ''
    xoaPwd.value = ''
    xoaPwdConfirm.value = ''
    sshPwd.value = ''
    sshPwdConfirm.value = ''
    enableSshAccount.value = true
  }
})

async function deploy() {
  if (selectedSr.value === undefined || selectedNetwork.value === undefined) {
    // Should not happen
    console.error('SR or network is undefined')
    return
  }

  if (
    ipStrategy.value === 'static' &&
    (ip.value === '' || netmask.value === '' || dns.value === '' || gateway.value === '')
  ) {
    // Should not happen
    console.error('Missing IP config')
    return
  }

  if (xoaUser.value === '' || xoaPwd.value === '') {
    // Should not happen
    console.error('Missing XOA user information')
    return
  }

  if (xoaPwd.value !== xoaPwdConfirm.value) {
    // TODO: use formal validation system
    openInvalidFieldModal(t('xoa-password-confirm-different'))
    return
  }

  if (enableSshAccount.value && sshPwd.value === '') {
    // Should not happen
    console.error('Missing XOA ssh credentials')
    return
  }

  if (enableSshAccount.value && sshPwd.value !== sshPwdConfirm.value) {
    // TODO: use form validation system
    openInvalidFieldModal(t('xoa-ssh-password-confirm-different'))
    return
  }

  deploying.value = true

  try {
    status.value = t('deploy-xoa-status:importing')

    // Option 1 (Vates): call VM.import directly — upstream behaviour, no proxy.
    // Options 2 & 3 (Ronivay / Custom): route through xoa-proxy which handles
    // gzip decompression and both HTTP/HTTPS sources (including self-signed TLS).
    const importUrl =
      imageSource.value === 'vates'
        ? XOA_VATES_IMAGE_URL
        : buildProxyUrl(
            imageSource.value === 'ronivay' ? XOA_RONIVAY_IMAGE_URL : xoaImageUrl.value,
            verifySsl.value
          )

    vmRef.value = (
      (await xapi.call('VM.import', [
        importUrl,
    // xoa-proxy.py (running on Dom0) fetches XOA_SOURCE_URL via HTTPS,
    // decompresses the .xva.gz on-the-fly, and serves the raw .xva over HTTP.
    // XAPI's VM.import then consumes the plain HTTP stream directly.
    const proxyUrl = buildProxyUrl(XOA_SOURCE_URL)

    vmRef.value = (
      (await xapi.call('VM.import', [
        proxyUrl,
        selectedSr.value.$ref,
        false, // full_restore
        false, // force
      ])) as string[]
    )[0]

    status.value = t('deploy-xoa-status:configuring')

    const [vifRef] = (await xapi.call('VM.get_VIFs', [vmRef.value])) as string[]

    if (vifRef !== undefined) {
    if (vifRef.length > 0) {
      await xapi.call('VIF.destroy', [vifRef])
    }

    if (!deploying.value) {
      return
    }

    const [device] = (await xapi.call('VM.get_allowed_VIF_devices', [vmRef.value])) as string[]
    await xapi.call('VIF.create', [
      {
        device,
        MAC: '',
        MTU: selectedNetwork.value.MTU,
        network: selectedNetwork.value.$ref,
        other_config: {},
        qos_algorithm_params: {},
        qos_algorithm_type: '',
        VM: vmRef.value,
      },
    ])

    if (!deploying.value) {
      return
    }

    const promises = [
      xapi.call('VM.add_to_xenstore_data', [
        vmRef.value,
        'vm-data/admin-account',
        JSON.stringify({ email: xoaUser.value, password: xoaPwd.value }),
      ]),
    ]

    if (ntp.value !== '') {
      promises.push(xapi.call('VM.add_to_xenstore_data', [vmRef.value, 'vm-data/ntp', ntp.value]))
    }

    // TODO: add host to servers with session token?

    if (ipStrategy.value === 'static') {
      promises.push(
        xapi.call('VM.add_to_xenstore_data', [vmRef.value, 'vm-data/ip', ip.value]),
        xapi.call('VM.add_to_xenstore_data', [vmRef.value, 'vm-data/netmask', netmask.value]),
        xapi.call('VM.add_to_xenstore_data', [vmRef.value, 'vm-data/gateway', gateway.value]),
        xapi.call('VM.add_to_xenstore_data', [vmRef.value, 'vm-data/dns', dns.value])
      )
    }

    if (enableSshAccount.value) {
      promises.push(
        xapi.call('VM.add_to_xenstore_data', [vmRef.value, 'vm-data/system-account-xoa-password', sshPwd.value])
      )
    }

    await Promise.all(promises)

    if (!deploying.value) {
      return
    }

    status.value = t('deploy-xoa-status:starting')

    await xapi.call('VM.start', [
      vmRef.value,
      false, // start_paused
      false, // force
    ])

    if (!deploying.value) {
      return
    }

    status.value = t('deploy-xoa-status:waiting')

    const metricsRef = await xapi.call('VM.get_guest_metrics', [vmRef.value])
    let attempts = 120
    let networks: { '0/ip': string } | undefined
    await new Promise(resolve => setTimeout(resolve, 10e3)) // Sleep 10s
    do {
      await new Promise(resolve => setTimeout(resolve, 1e3)) // Sleep 1s
      networks = await xapi.call('VM_guest_metrics.get_networks', [metricsRef])
      if (!deploying.value) {
        return
      }
    } while (--attempts > 0 && networks?.['0/ip'] === undefined)

    if (attempts === 0 || networks === undefined) {
      status.value = t('deploy-xoa-status:not-responding')
      return
    }

    await Promise.all(
      ['admin-account', 'dns', 'gateway', 'ip', 'netmask', 'xoa-updater-credentials'].map(key =>
        xapi.call('VM.remove_from_xenstore_data', [vmRef.value, `vm-data/${key}`])
      )
    )

    status.value = t('deploy-xoa-status:ready')

    // TODO: handle IPv6
    url.value = `https://${networks['0/ip']}`
  } catch (err: any) {
    console.error(err)
    error.value = err?.message ?? err?.code ?? 'Unknown error'
  }
}

async function cancel() {
  const _vmRef = vmRef.value
  resetValues()
  if (_vmRef !== undefined) {
    try {
      await xapi.call('VM.destroy', [_vmRef])
    } catch (err) {
      console.error(err)
    }
  }
}
</script>

<style lang="postcss" scoped>
.card-view {
  flex-direction: column;
}

.row {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  column-gap: 10rem;
  margin-bottom: 2.4rem;

  & > div {
    flex: 1;
    max-width: calc(50% - 4rem);
  }
}

.image-source-row {
  display: flex;
  gap: 1rem;
  align-items: center;
  width: 100%;
}

.image-source-select {
  height: 3.6rem;
  padding: 0 1rem;
  border: 1px solid var(--color-neutral-border-strong);
  border-radius: 0.4rem;
  background: var(--color-neutral-background-primary);
  color: var(--color-neutral-txt-primary);
  font-size: inherit;
  cursor: pointer;
  flex-shrink: 0;
}

.custom-url-input {
  flex: 1;
}

.input-container * {
  vertical-align: middle;
}

.not-available,
.status {
  display: flex;
  flex-direction: column;
  gap: 42px;
  justify-content: center;
  align-items: center;
  min-height: 76.5vh;
  color: var(--color-brand-txt-base);
  text-align: center;
  padding: 5rem;
  margin: auto;

  h2 {
    margin-bottom: 1rem;
  }

  * {
    max-width: 100%;
  }
}

.not-available {
  font-size: 2rem;
}

.status {
  color: var(--color-neutral-txt-primary);
}

.success {
  color: var(--color-success-txt-base);
}

.danger {
  color: var(--color-danger-txt-base);
}

.success,
.danger {
  &.ui-icon {
    font-size: 3rem;
  }
}

.error {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 0.5em;
}

.warning {
  color: var(--color-warning-txt-base);
}
</style>
