// 支付功能页模板（PaymentPage）v2 —— 支付二期
// 槽位：CHANNELS_JSON / BROKEN_JSON / DEAD_JSON / BLANK_JSON / AMOUNT / POPUP_AMOUNT / PAY_PWD
//       ERR_TEXT / ERR_AGREE / ERR_PWD / ALL_BROKEN / ALL_BROKEN_TEXT / TWICE_POPUP
//       MISMATCH / CANCEL_ALERT_TEXT / PAY_TIMEOUT_SEC / PAY_TIMEOUT_TEXT
//       REFUND_ENABLED / REFUND_TEXT / ORDER_TITLE / APP_NAME / SUCCESS_TEXT / TASK_ID
// 语义：点击渠道 → 拉起品牌支付弹窗（拉起成功锚点）→ mock 密码 → 成功页（可选退款流）。
// 故障/风控形态：BROKEN 拉起失败、DEAD 死弹窗、BLANK 空白页、ALL_BROKEN 全故障、
//               TWICE 二次确认、MISMATCH 金额不一致（应取消）、PAY_TIMEOUT 支付超时、REFUND 退款流。
interface ChInfo {
  key: string
  label: string
  color?: string
  decoy?: boolean
}

@Entry
@Component
struct Index {
  @State agree: boolean = false
  @State chan: string = ''
  @State err: string = ''
  @State pwd: string = ''
  @State done: boolean = false
  @State blank: boolean = false
  @State cancelAlert: boolean = false
  @State refund: boolean = false
  @State left: number = 0
  private timerId: number = -1
  private CHANNELS: ChInfo[] = JSON.parse('{{CHANNELS_JSON}}') as ChInfo[]
  private BROKEN: string[] = JSON.parse('{{BROKEN_JSON}}') as string[]
  private DEAD: string[] = JSON.parse('{{DEAD_JSON}}') as string[]
  private BLANK: string[] = JSON.parse('{{BLANK_JSON}}') as string[]
  private ALL_BROKEN: string = '{{ALL_BROKEN}}'
  private TWICE: string = '{{TWICE_POPUP}}'
  private MISMATCH: string = '{{MISMATCH}}'
  private REFUND_ENABLED: string = '{{REFUND_ENABLED}}'
  private AGREE_TRAP: string = '{{AGREE_TRAP}}'
  private TIMEOUT_SEC: number = parseInt('{{PAY_TIMEOUT_SEC}}', 10)

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

  // 视觉门控：文字相同、仅颜色区分正规/假冒入口（假冒入口点击即拦截）
  tapChannelObj(c: ChInfo): void {
    if (c.decoy === true) {
      this.err = '该入口不是正规支付通道，已为你拦截'
      this.chan = 'fail'
      return
    }
    this.tapChannel(c.key)
  }

  stopTimer(): void {
    if (this.timerId !== -1) {
      clearInterval(this.timerId)
      this.timerId = -1
    }
  }

  startTimer(): void {
    this.stopTimer()
    if (this.TIMEOUT_SEC > 0) {
      this.left = this.TIMEOUT_SEC
      this.timerId = setInterval(() => {
        this.left--
        if (this.left <= 0) {
          this.stopTimer()
          this.chan = 'timeout'
          this.pwd = ''
        }
      }, 1000)
    }
  }

  tapChannel(key: string): void {
    this.err = ''
    if (this.ALL_BROKEN === 'true') {
      this.err = '{{ALL_BROKEN_TEXT}}'
      this.chan = 'none'
      return
    }
    if (this.BROKEN.includes(key)) {
      this.err = '{{ERR_TEXT}}'.replace('{CH}', this.label(key))
      this.chan = 'fail'
      return
    }
    if (this.BLANK.includes(key)) {
      this.blank = true
      this.chan = key
      return
    }
    if (this.DEAD.includes(key)) {
      this.chan = key + ':dead'
      return
    }
    this.chan = key
    this.startTimer()
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
    if (this.TWICE === 'true' && this.chan.indexOf(':twice') < 0) {
      this.chan = this.chan + ':twice'
      return
    }
    this.stopTimer()
    this.done = true
  }

  cancelPay(): void {
    this.stopTimer()
    if (this.MISMATCH === 'true') {
      this.chan = ''
      this.pwd = ''
      this.cancelAlert = true
      return
    }
    this.chan = ''
    this.pwd = ''
    this.err = ''
  }

  onBackPress(): boolean {
    if (this.chan !== '' || this.blank) {
      this.stopTimer()
      this.chan = ''
      this.blank = false
      this.pwd = ''
      return true
    }
    return false
  }

  aboutToDisappear(): void {
    this.stopTimer()
  }

  build() {
    Column() {
      if (this.refund) {
        Column({ space: 12 }) {
          Text('{{REFUND_TEXT}}').fontSize(16).id('refund_marker')
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else if (this.done) {
        Column({ space: 12 }) {
          Text('{{APP_NAME}}').fontSize(18).fontWeight(FontWeight.Bold)
          Text('{{SUCCESS_TEXT}}').fontSize(16).id('welcome_marker')
          if (this.REFUND_ENABLED === 'true') {
            Button('申请退款').height(44).backgroundColor('#FFF3E0').fontColor('#E65100')
              .onClick(() => { this.refund = true })
          }
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else if (this.cancelAlert) {
        Column({ space: 12 }) {
          Text('{{CANCEL_ALERT_TEXT}}').fontSize(15).fontColor('#FF3B30')
            .id('cancel_alert_marker')
          Button('我知道了').height(44)
            .onClick(() => { this.cancelAlert = false })
        }.width('86%').padding(16).margin({ top: 260 })
      } else if (this.chan === 'timeout') {
        Column({ space: 12 }) {
          Text('{{PAY_TIMEOUT_TEXT}}').fontSize(16).fontColor('#FF3B30')
            .id('timeout_marker')
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('86%').padding(16).margin({ top: 260 })
      } else if (this.chan === 'fail') {
        Column({ space: 12 }) {
          Text(this.err).fontSize(15).fontColor('#FF3B30')
          Button('更换支付方式').height(44)
            .onClick(() => { this.chan = ''; this.err = '' })
        }.width('86%').padding(16).margin({ top: 200 })
      } else if (this.chan === 'none') {
        Column({ space: 12 }) {
          Text('{{ALL_BROKEN_TEXT}}').fontSize(16).fontColor('#FF3B30')
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('86%').padding(16).margin({ top: 260 })
      } else if (this.chan.indexOf(':dead') >= 0) {
        Column({ space: 12 }) {
          Text(this.label(this.chan.split(':')[0])).fontSize(18).fontWeight(FontWeight.Bold)
          Text('¥ {{POPUP_AMOUNT}}').fontSize(16)
          Text('（弹窗内容异常，无确认按钮）').fontSize(12).fontColor('#999999')
        }.width('70%').padding(24).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: 300 })
      } else if (this.blank) {
        Column({ space: 8 }) {
          Text('').fontSize(14)
        }.width('100%').height('60%').justifyContent(FlexAlign.Center)
      } else if (this.chan.indexOf(':twice') >= 0) {
        Column({ space: 14 }) {
          Text('再次确认支付').fontSize(18).fontWeight(FontWeight.Bold)
          Text('订单金额：¥ {{POPUP_AMOUNT}}').fontSize(16)
          if (this.TIMEOUT_SEC > 0) {
            Text('剩余支付时间：' + this.left + 's').fontSize(13).fontColor('#FF9500')
          }
          Button('确认支付').width('100%').height(46)
            .onClick(() => { this.stopTimer(); this.done = true })
          Button('返回修改').height(40).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.chan = this.chan.split(':')[0]; this.pwd = '' })
        }.width('80%').padding(20).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: {{POPUP_MARGIN}} })
      } else if (this.chan !== '') {
        // 渠道弹窗（拉起成功锚点）
        Column({ space: 14 }) {
          Text(this.label(this.chan)).fontSize(20).fontWeight(FontWeight.Bold)
            .id('pay_popup_' + this.chan)
          Text('订单金额：¥ {{POPUP_AMOUNT}}').fontSize(16)
          if (this.TIMEOUT_SEC > 0) {
            Text('剩余支付时间：' + this.left + 's').fontSize(13).fontColor('#FF9500')
          }
          TextInput({ placeholder: '请输入支付密码' })
            .maxLength(6)
            .type(InputType.Password)
            .onChange((v: string) => { this.pwd = v })
          Button('确认支付').width('100%').height(46)
            .onClick(() => { this.pay() })
          if (this.err !== '') { Text(this.err).fontSize(13).fontColor('#FF3B30') }
          Button('取消').height(40).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.cancelPay() })
        }.width('80%').padding(20).backgroundColor('#FFFFFF').borderRadius(12).margin({ top: {{POPUP_MARGIN}} })
      } else {
        // 主支付页
        Column({ space: 14 }) {
          Text('订单支付').fontSize(22).fontWeight(FontWeight.Bold)
          Text('商品：{{ORDER_TITLE}}').fontSize(14)
          Text('应付金额：¥ {{AMOUNT}}').fontSize(16).fontWeight(FontWeight.Bold)
          Row({ space: 6 }) {
            Checkbox().select(this.agree).onChange((v: boolean) => { this.agree = v })
            Text((this.agree ? '✓ ' : '〇 ') + '我已阅读并同意《支付协议》').fontSize(12)
          }.width('100%')
          .onClick(() => {
            // 默认：整行可点（真机实测——若只有小方块可点，视觉模型会反复点文字标签而卡死）
            // AGREE_TRAP='true' 时还原该缺陷，作为 B11 精准点击陷阱
            if (this.AGREE_TRAP !== 'true') { this.agree = true }
          })
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
    .width('100%').height('100%')
  }
}