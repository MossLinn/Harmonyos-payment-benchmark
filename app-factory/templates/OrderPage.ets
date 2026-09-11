// 订单确认页模板（OrderPage）—— CHECKOUT_PAGE='true' 时作为 pages/Index
// 语义：订单摘要 → 去支付（router.push 收银台 pages/Checkout）→ 支付成功后返回本页显示已完成态。
// 返回语义：收银台按系统返回/返回订单 回到本页；取消订单提供 cancel marker（诊断类任务用）。
// 槽位（PaymentPage 槽位子集，gen_hap 默认槽位机制同样生效）：
//       ORDER_TITLE / AMOUNT / APP_NAME / TASK_ID
import { router } from '@kit.ArkUI';

@Entry
@Component
struct Index {
  @StorageLink('pay_result') payResult: string = ''
  @State cancelled: boolean = false

  build() {
    Column({ space: 14 }) {
      if (this.cancelled) {
        Column({ space: 12 }) {
          Text('订单已取消').fontSize(18).fontWeight(FontWeight.Bold).id('order_cancel_marker')
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
          Button('返回').height(40).backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.cancelled = false })
        }.width('86%').padding(16).margin({ top: 240 })
      } else if (this.payResult === 'success') {
        Column({ space: 12 }) {
          Text('{{APP_NAME}}').fontSize(18).fontWeight(FontWeight.Bold)
          Text('支付成功，订单已完成').fontSize(16).id('order_paid_marker')
          Text('{{TASK_ID}}').fontSize(11).fontColor('#BBBBBB')
        }.width('100%').height('100%').justifyContent(FlexAlign.Center)
      } else {
        Column({ space: 14 }) {
          Text('确认订单').fontSize(22).fontWeight(FontWeight.Bold).id('order_marker')
          Text('商品：{{ORDER_TITLE}}').fontSize(14)
          Text('订单金额：¥ {{AMOUNT}}').fontSize(16).fontWeight(FontWeight.Bold)
          Text('订单编号：{{TASK_ID}}').fontSize(12).fontColor('#999999')
          Button('去支付').width('100%').height(48)
            .onClick(() => { router.pushUrl({ url: 'pages/Checkout' }) })
          Button('取消订单').width('100%').height(44)
            .backgroundColor('#F5F5F5').fontColor('#333333')
            .onClick(() => { this.cancelled = true })
        }.width('86%').padding(16)
      }
    }
    .width('100%').height('100%')
  }
}