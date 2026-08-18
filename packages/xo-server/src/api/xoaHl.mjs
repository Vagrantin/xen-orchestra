import { execa } from 'execa'
import { readFile } from 'fs/promises'

const STATUS_FILE = '/run/xoa-hl/status'

// -------------------------------------------------------------------

export async function getVersion() {
  try {
    const { stdout } = await execa('rpm', ['-q', '--qf', '%{VERSION}-%{RELEASE}\\n', 'xoa-hl'])
    return stdout.trim()
  } catch (error) {
    // not running on the appliance, or package not found
    return { error: 'unknown' }
  }
}
getVersion.permission = 'admin'
getVersion.description = 'get the installed version of xoa-hl'

// -------------------------------------------------------------------

export async function checkForUpdate() {
  await execa('sudo', ['systemctl', 'start', 'xoa-hl-check-update.service'])
  return { started: true }
}
checkForUpdate.permission = 'admin'
checkForUpdate.description = 'queue a check for xoa-hl updates'

// -------------------------------------------------------------------

export async function getUpdateStatus() {
  let content
  try {
    content = await readFile(STATUS_FILE, 'utf8')
  } catch (error) {
    // never checked yet
    return { checking: false, updateAvailable: false }
  }

  const status = content.trim()
  if (status === 'UP_TO_DATE') {
    return { checking: false, updateAvailable: false }
  }

  const match = status.match(/^AVAILABLE (.+)$/)
  if (match !== null) {
    return { checking: false, updateAvailable: true, latestVersion: match[1] }
  }

  return { checking: false, updateAvailable: false }
}
getUpdateStatus.permission = 'admin'
getUpdateStatus.description = 'get the latest xoa-hl update check result'

// -------------------------------------------------------------------

export async function startUpdate() {
  await execa('sudo', ['systemctl', 'start', 'xoa-hl-update.service'])
  return { started: true }
}
startUpdate.permission = 'admin'
startUpdate.description = 'run the xoa-hl update, resolves once it has finished'

// -------------------------------------------------------------------

export async function getUpdateProgress() {
  const [{ stdout: showOut }, { stdout: logOut }] = await Promise.all([
    execa('systemctl', [
      'show',
      'xoa-hl-update.service',
      '--property=ActiveState,SubState,ExecMainStatus,ExecMainCode',
    ]),
    execa('journalctl', ['-u', 'xoa-hl-update.service', '-n', '50', '--no-pager', '-o', 'cat']),
  ])

  const properties = {}
  for (const line of showOut.split('\n')) {
    const i = line.indexOf('=')
    if (i !== -1) {
      properties[line.slice(0, i)] = line.slice(i + 1)
    }
  }

  return {
    activeState: properties.ActiveState,
    subState: properties.SubState,
    exitStatus: properties.ExecMainStatus,
    log: logOut.split('\n'),
  }
}
getUpdateProgress.permission = 'admin'
getUpdateProgress.description = 'get the state and log tail of the xoa-hl update service'
