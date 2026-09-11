// 收银台模板（ShopCashier）—— 页 4/5（复用支付 v3 机制：渠道/安全键盘/风控点选/短信 OTP）
// 金额来自 AppStorage.order_total（订单确认页提交时写入）
// 槽位：CHANNELS_JSON / BROKEN_JSON / PAY_PWD / ERR_TEXT / ERR_AGREE / ERR_PWD
//       RISK_CAPTCHA / RISK_SEQ / SMS_OTP / OTP_CODE / RESEND_SEC / OTP_ERROR / TASK_ID / APP_NAME / POPUP_MARGIN
import { router } from '@kit.ArkUI';

interface ChInfo {
  key: string
  label: string
  color?: string
  decoy?: boolean
}

@Entry
@Component
struct Cashier {
  @State agree: boolean = false
  @State chan: string = ''
  @State err: string = ''
  @State pwd: string = ''
  @State otp: string = ''
  @State done: boolean = false
  @State otpLeft: number = 0
  @State riskProgress: number = 0
  @State padDigits: string[] = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '退格', '0', '清空']
  @State riskCells: string[] = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
  @StorageLink('order_total') orderTotal: string = '0.00'
  private timerId: number = -1
  private otpTimerId: number = -1
  private twiceDone: boolean = false
  private riskDone: boolean = false
  private otpDone: boolean = false
  private CHANNELS: ChInfo[] = JSON.parse('{{CHANNELS_JSON}}') as ChInfo[]
  private BROKEN: string[] = JSON.parse('{{BROKEN_JSON}}') as string[]
  private TWICE: string = '{{TWICE_POPUP}}'
  private RISK_CAPTCHA: string = '{{RISK_CAPTCHA}}'
  private RISK_SEQ: string[] = '{{RISK_SEQ}}'.split(',')
  private SMS_OTP: string = '{{SMS_OTP}}'
  private OTP_CODE: string = '{{OTP_CODE}}'
  private RESEND_SEC: number = parseInt('{{RESEND_SEC}}', 10)

  aboutToAppear(): void {
    this.padDigits = this.shuffled('{{TASK_ID}}',
      ['1', '2', '3', '4', '5', '6', '7', '8', '9', '退格', '0', '清空'])
    this.riskCells = this.shuffled('{{TASK_ID}}#risk',
      ['1', '2', '3', '4', '5', '6', '7', '8', '9'])
  }

  shuffled(seed: string, base: string[]): string[] {
    let h: number = 7
    for (let i = 0; i < seed.length; i++) {
      h = (h * 131 + seed.charCodeAt(i)) % 2147483647
    }
    const arr: string[] = base.slice()
    for (let i = arr.length - 1; i > 0; i--) {
      h = (h * 48271) % 2147483647
      const j: number = h % (i + 1)
      const t: string = arr[i]
      arr[i] = arr[j]
      arr[j] = t
    }
    return arr
  }

  label(key: string): string {
    if (key === 'wechat') { return '微信支付' }
    if (key === 'alipay') { return '支付宝' }
    if (key === 'bankcard') { return '银行卡支付' }
    return '华为支付'
  }

  bgOf(c: ChInfo): string {
    if (c.color !== undefined && c.color !== '') { return c.color }
    return '#FFFFFF'
  }

  fgOf(c: ChInfo): string {
    if (c.color !== undefined && c.color !== '') { return '#FFFFFF' }
    return '#000000'
  }

  maskOf(v: string): string {
    let s: string = ''
    for (let i = 0; i < v.length; i++) { s += '●' }
    return s
  }

  stopOtpTimer(): void {
    if (this.otpTimerId !== -1) {
      clearInterval(this.otpTimerId)
      this.otpTimerId = -1
    }
  }

  startOtpTimer(): void {
    this.stopOtpTimer()
    this.otpLeft = this.RESEND_SEC
    this.otpTimerId = setInterval(() => {
      this.otpLeft--
      if (this.otpLeft <= 0) { this.stopOtpTimer() }
    }, 1000)
  }

  tapChannelObj(c: ChInfo): void {
    if (c.decoy === true) {
      this.err = '该入口不是正规支付通道，已为你拦截'
      this.chan = 'fail'
      return
    }
    this.tapChannel(c.key)
  }

  tapChannel(key: string): void {
    this.err = ''
    if (this.BROKEN.includes(key)) {
      this.err = '{{ERR_TEXT}}'.replace('{CH}', this.label(key))
      this.chan = 'fail'
      return
    }
    this.chan = key
  }

  pay(): void {
    if (!this.agree) {
      this.err = '{{ERR_AGREE}}'
      return
    }
    if (this.pwd !== '{{PAY_PWD}}') {
      this.err = '{{ERR_PWD}}'
      return
    }
    this.err = ''
    const base: string = this.chan.split(':')[0]
    if (this.TWICE === 'true' && !this.twiceDone) {
      this.chan = base + ':twice'
      return
    }
    if (this.RISK_CAPTCHA !== 'none' && !this.riskDone) {
      this.chan = base + ':risk'
      return
    }
    if (this.SMS_OTP === 'true' && !this.otpDone) {
      this.chan = base + ':otp'
      this.startOtpTimer()
      return
    }
    this.stopOtpTimer()
    this.done = true
    AppStorage.setOrCreate('pay_result', 'success')
    // 真实支付动线：成功页短暂展示后自动进入订单结果页（不依赖 agent 手动最后一跳）
    setTimeout(() => {
      router.pushUrl({ url: 'pages/Result' })
    }, 1500)
  }

  padTap(d: string, target: string): void {
    if (d === '退格') {
      if (target === 'otp') { this.otp = this.otp.substring(0, this.otp.length - 1) }
      else { this.pwd = this.pwd.substring(0, this.pwd.length - 1) }
      return
    }
    if (d === '清空') {
      if (target === 'otp') { this.otp = '' } else { this.pwd = '' }
      return
    }
    if (target === 'otp') {
      if (this.otp.length < this.OTP_CODE.length) { this.otp += d }
    } else {
      if (this.pwd.length < 6) { this.pwd += d }
    }
  }

  riskTap(d: string): void {
    if (this.riskDone) { return }
    if (this.riskProgress >= this.RISK_SEQ.length) { return }
    if (d === this.RISK_SEQ[this.riskProgress]) {
      this.riskProgress++
      this.err = ''
      if (this.riskProgress === this.RISK_SEQ.length) {
        this.riskDone = true
        this.pay()
      }
    } else {
      this.riskProgress = 0
      this.err = '验证顺序错误，请重新点击'
    }
  }

  submitOtp(): void {
    if (this.otp !== this.OTP_CODE) {
      this.err = '{{OTP_ERROR}}'
      this.otp = ''
      return
    }
    this.otpDone = true
    this.pay()
  }

  resendOtp(): void {
    if (this.otpLeft > 0) { return }
    this.otp = ''
    this.startOtpTimer()
  }

  cancelPay(): void {
    this.stopOtpTimer()
    this.twiceDone = false
    this.riskDone = false
    this.otpDone = false
    this.riskProgress = 0
    this.chan = ''
    this.pwd = ''
    this.otp = ''
    this.err = ''
  }

  onBackPress(): boolean {
    if (this.chan !== '') {
      this.cancelPay()
      return true
    }
    return false
  }

  aboutToDisappear(): void {
    this.stopOtpTimer()
  }

  @Builder
  numPad(target: string) {
    Column({ space: 8 }) {
      Grid() {
        ForEach(this.padDigits, (d: string) => {
          GridItem() {
            Button(d)
              .width('100%').height(44)
              .fontSize(d.length > 1 ? 13 : 18)
              .backgroundColor(d === '清空' ? '#F5F5F5' : '#FFFFFF')
              .fontColor(d === '清空' ? '#666666' : '#20242C')
              .border({ width: 1, color: '#DDDDDD' })
              .onClick(() => { this.padTap(d, target) })
          }
        }, (d: string) => d)
      }
      .columnsTemplate('1fr 1fr 1fr')
      .rowsGap(6).columnsGap(6)
      .height(160)
    }.width('100%').padding(8).backgroundColor('#F7F8FA').borderRadius(8).id('pay_keypad')
  }

  @Builder
  riskGrid() {
    Grid() {
      ForEach(this.riskCells, (d: string) => {
        GridItem() {
          Text(d)
            .fontSize(22).fontWeight(FontWeight.Bold)
            .textAlign(TextAlign.Center)
            .width('100%').height(52)
            .backgroundColor('#EEF1F7').borderRadius(8)
            .onClick(() => { this.riskTap(d) })
        }
      }, (d: string) => d)
    }
    .columnsTemplate('1fr 1fr 1fr')
    .rowsGap(8).columnsGap(8)
    .height(180)
    .id('risk_grid')
  }

  build() {
    Column() {
      Row({ space: 10 }) {
        Text('←').fontSize(20).width(36).height(36).textAlign(TextAlign.Center)
          .onClick(() => { router.back() })
        Text('收银台').fontSize(17).fontWeight(FontWeight.Bold).id('cashier_marker')
      }.width('92%').margin({ top: 8 })

      if (this.done) {
        Column({ space: 12 }) {
          Text('✅').fontSize(46)
          Text('{{APP_NAME}}').fontSize(17).fontWeight(FontWeight.Bold)
          Text('支付成功').fontSize(16).id('welcome_marker')
          Text('订单编号：{{TASK_ID}}').fontSize(12).fontColor('#999999')
          Button('查看订单结果').width('80%').height(46)
            .id('to_result')
            .onClick(() => { router.pushUrl({ url: 'pages/Result' }) })
          Button('返回首页').width('80%').height(44).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => {
              router.clear()
              router.pushUrl({ url: 'pages/Index' })
            })
        }.width('100%').layoutWeight(1).justifyContent(FlexAlign.Center)
      } else if (this.chan === 'fail') {
        Column({ space: 12 }) {
          Text(this.err).fontSize(15).fontColor('#FF3B30')
          Button('更换支付方式').height(44).id('retry_channel')
            .onClick(() => { this.chan = ''; this.err = '' })
        }.width('86%').padding(16).margin({ top: 200 })
      } else if (this.chan.indexOf(':otp') >= 0) {
        Column({ space: 12 }) {
          Text('短信验证码').fontSize(18).fontWeight(FontWeight.Bold).id('otp_marker')
          Text('验证码已发送至本机，请输入 6 位验证码').fontSize(13).fontColor('#666666')
          Text(this.maskOf(this.otp)).fontSize(24).letterSpacing(8).id('otp_mask')
          if (this.err !== '') { Text(this.err).fontSize(13).fontColor('#FF3B30') }
          this.numPad('otp')
          Button('确认支付').width('100%').height(46).onClick(() => { this.submitOtp() })
          Button(this.otpLeft > 0 ? `重新发送(${this.otpLeft}s)` : '重新发送验证码')
            .height(40).backgroundColor('#F5F5F5').fontColor(this.otpLeft > 0 ? '#AAAAAA' : '#1F5FD0')
            .id('otp_resend')
            .onClick(() => { this.resendOtp() })
          Button('取消').height(40).backgroundColor('#FFFFFF').fontColor('#333333')
            .onClick(() => { this.cancelPay() })
        }.width('84%').padding(16).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: 60 })
      } else if (this.chan.indexOf(':risk') >= 0) {
        Column({ space: 12 }) {
          Text('人机验证').fontSize(18).fontWeight(FontWeight.Bold).id('risk_title')
          Text('请依次点击：' + this.RISK_SEQ.join('  ')).fontSize(15).fontColor('#1F5FD0')
            .id('risk_seq_hint')
          this.riskGrid()
          if (this.err !== '') { Text(this.err).fontSize(13).fontColor('#FF3B30') }
          if (this.riskDone) {
            Text('人机验证通过').fontSize(14).fontColor('#16865A').id('risk_passed_marker')
          }
          Button('取消').height(40).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.cancelPay() })
        }.width('84%').padding(16).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: 80 })
      } else if (this.chan.indexOf(':twice') >= 0) {
        Column({ space: 14 }) {
          Text('再次确认支付').fontSize(18).fontWeight(FontWeight.Bold)
          Text('支付金额：¥' + this.orderTotal).fontSize(16)
          Button('确认支付').width('100%').height(46)
            .onClick(() => { this.twiceDone = true; this.pay() })
          Button('返回修改').height(40).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.chan = this.chan.split(':')[0]; this.pwd = '' })
        }.width('80%').padding(20).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: {{POPUP_MARGIN}} })
      } else if (this.chan !== '') {
        Column({ space: 14 }) {
          Text(this.label(this.chan)).fontSize(20).fontWeight(FontWeight.Bold)
            .id('pay_popup_' + this.chan)
          Text('支付金额：¥' + this.orderTotal).fontSize(16).id('cashier_amount')
          Row({ space: 6 }) {
            Checkbox().select(this.agree).onChange((v: boolean) => { this.agree = v })
            Text((this.agree ? '✓ ' : '〇 ') + '我已阅读并同意《支付协议》').fontSize(12)
          }.width('100%')
          .onClick(() => { this.agree = true })
          if (this.err !== '') { Text(this.err).fontSize(13).fontColor('#FF3B30') }
          Text(this.maskOf(this.pwd)).fontSize(24).letterSpacing(8).id('pwd_mask')
          if (this.err !== '') { Text(this.err).fontSize(13).fontColor('#FF3B30') }
          this.numPad('pwd')
          Button('确认支付').width('100%').height(46).onClick(() => { this.pay() })
          Button('取消').height(40).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.cancelPay() })
        }.width('80%').padding(20).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: {{POPUP_MARGIN}} })
      } else {
        // 收银台主页
        Column({ space: 14 }) {
          Text('应付金额').fontSize(14).fontColor('#666666')
          Text('¥' + this.orderTotal).fontSize(30).fontColor('#E4393C').fontWeight(FontWeight.Bold)
            .id('cashier_total')
          Row({ space: 6 }) {
            Checkbox().select(this.agree).onChange((v: boolean) => { this.agree = v })
            Text((this.agree ? '✓ ' : '〇 ') + '我已阅读并同意《支付协议》').fontSize(12)
          }.width('100%')
          .onClick(() => { this.agree = true })
          Text('选择支付方式').fontSize(14).fontColor('#666666')
          ForEach(this.CHANNELS, (c: ChInfo) => {
            Button(c.label).width('100%').height(52)
              .fontSize(15)
              .backgroundColor(this.bgOf(c))
              .fontColor(this.fgOf(c))
              .onClick(() => { this.tapChannelObj(c) })
          })
          if (this.err !== '') { Text(this.err).fontSize(13).fontColor('#FF3B30') }
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('86%').padding(16)
      }
    }
    .width('100%').height('100%').backgroundColor('#F5F6F8')
  }
}